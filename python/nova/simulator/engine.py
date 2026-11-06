"""
Decision Simulator - transparent unit-economics model for "what if" questions.

    base_{t+1}   = base_t * (1 - churn_m) + new_t                 (active customer base, 90-day definition)
    new_t        = paid_new + organic_new
                   paid_new    = marketing_acq_spend / CAC
                   organic_new = observed organic new customers * (1 + conversion_change)
    orders_t     = base_t * orders_per_customer * (1 + conversion_change)
    gross_t      = orders_t * AOV_gross
    net_t        = gross_t * (1 - discount_rate - refund_rate)
    GP_t         = net_t - gross_t * cogs_pct
    CM_t         = GP_t - orders_t * variable_cost_per_order
    CM_after_mkt = CM_t - marketing_spend
    LTV (CM)     = CM per customer-month / churn_m                (geometric lifetime)

LABELS: every number is one of  observed | assumption | forecast (baseline) | estimate (scenario).
Simulated values are NEVER written as actuals. The model has no demand elasticity: if you cut discounts
you must ALSO state what you believe happens to conversion. The simulator refuses to invent that.

CLI:  python -m nova.simulator.engine --example
      python -m nova.simulator.engine --discount-pp -2 --conversion-pct -3 --cac-pct 10
"""
import argparse
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from nova.common.db import read_sql, write_df
from nova.common.report import md_table, write

MONTHS = 12


@dataclass
class Baseline:
    base_customers: float
    churn_m: float
    orders_per_customer: float
    aov_gross: float
    discount_rate: float
    refund_rate: float
    cogs_pct: float
    variable_cost_per_order: float
    marketing_spend: float
    acq_spend: float
    cac: float
    organic_new: float
    sd: dict


@dataclass
class Scenario:
    name: str = "baseline"
    retention_pp: float = 0.0        # + = lower monthly churn by X percentage points
    conversion_pct: float = 0.0      # relative change in order frequency & organic acquisition
    aov_pct: float = 0.0
    cac_pct: float = 0.0
    refund_pp: float = 0.0
    discount_pp: float = 0.0
    marketing_pct: float = 0.0


def observed_baseline(months=("2025-07-01", "2025-12-01")) -> Baseline:
    m = read_sql("select * from metrics.metrics_monthly where month between :a and :b order by month",
                 dict(a=months[0], b=months[1]))
    base = read_sql("""with co as (select distinct customer_id, order_date from marts.fct_orders
                                   where is_countable and customer_id is not null)
                       select count(distinct customer_id) as n from co where order_date > date '2025-12-31' - 90""").n.iat[0]
    churn90 = read_sql("select churn_rate_90d from metrics.metrics_monthly where churn_rate_90d is not null "
                       "order by month desc limit 3").churn_rate_90d.astype(float).mean()
    churn_m = 1 - (1 - churn90) ** (1 / 3)
    base_by_m = read_sql("""select month, count(*) filter (where is_active) as active from marts.fct_customer_monthly
                            group by 1""")
    m = m.merge(base_by_m, on="month")
    per = lambda a, b: (m[a].astype(float) / m[b].astype(float))
    ship_net = read_sql("""select sum(variable_fulfilment_cost - shipping_fee_collected) / sum(completed_orders) as v
                           from marts.fct_orders where is_countable and order_date >= :a""", dict(a=months[0])).v.iat[0]
    organic = (m.new_customers - m.paid_new_customers).astype(float).mean()
    series = dict(orders_per_customer=per("orders", "active") * (m.active / base),  # scaled to 90d base
                  aov_gross=per("gross_revenue", "orders"), discount_rate=per("coupon_discount", "gross_revenue"),
                  refund_rate=per("return_refund_amount", "gross_revenue"),
                  cogs_pct=(m.gross_revenue - m.coupon_discount - m.return_refund_amount - m.gross_profit).astype(float)
                  / m.gross_revenue.astype(float))
    means = {k: float(v.mean()) for k, v in series.items()}
    means["orders_per_customer"] = float(m.orders.astype(float).mean() / base)
    sd = {k: float(v.std()) for k, v in series.items()}
    sd["orders_per_customer"] = float((m.orders.astype(float) / base).std())
    sd["churn_m"] = churn_m * 0.1
    return Baseline(base_customers=float(base), churn_m=float(churn_m), variable_cost_per_order=float(ship_net),
                    marketing_spend=float(m.marketing_spend.astype(float).mean()),
                    acq_spend=float(m.acquisition_spend.astype(float).mean()),
                    cac=float(m.acquisition_spend.astype(float).sum() / m.paid_new_customers.astype(float).sum()),
                    organic_new=float(organic), sd=sd, **means)


def project(b: Baseline, s: Scenario, params: dict | None = None) -> pd.DataFrame:
    p = dict(asdict(b)) | (params or {})
    churn = max(p["churn_m"] - s.retention_pp / 100, 0.001)
    conv = 1 + s.conversion_pct / 100
    aov = p["aov_gross"] * (1 + s.aov_pct / 100)
    disc = max(p["discount_rate"] + s.discount_pp / 100, 0)
    refund = max(p["refund_rate"] + s.refund_pp / 100, 0)
    cac = p["cac"] * (1 + s.cac_pct / 100)
    mkt = p["marketing_spend"] * (1 + s.marketing_pct / 100)
    acq = p["acq_spend"] * (1 + s.marketing_pct / 100)
    base = p["base_customers"]
    rows = []
    for t in range(1, MONTHS + 1):
        new = acq / cac + p["organic_new"] * conv
        orders = base * p["orders_per_customer"] * conv
        gross = orders * aov
        net = gross * (1 - disc - refund)
        gp = net - gross * p["cogs_pct"]
        cm = gp - orders * p["variable_cost_per_order"]
        rows.append(dict(month_ahead=t, base_customers=base, new_customers=new, orders=orders, gross_revenue=gross,
                         net_revenue=net, gross_profit=gp, contribution_margin=cm, marketing_spend=mkt,
                         cm_after_marketing=cm - mkt,
                         ltv_cm=(cm / base) / churn if base else np.nan, cac=cac))
        base = base * (1 - churn) + new
    df = pd.DataFrame(rows)
    df["ltv_to_cac"] = df.ltv_cm / df.cac
    return df


def monte_carlo(b: Baseline, s: Scenario, n=500, seed=1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    tot = []
    for _ in range(n):
        draw = {k: max(getattr(b, k) + rng.normal(0, sd), 1e-6) for k, sd in b.sd.items()}
        r = project(b, s, draw)
        tot.append(dict(net_revenue=r.net_revenue.sum(), contribution_margin=r.contribution_margin.sum(),
                        cm_after_marketing=r.cm_after_marketing.sum(), end_customers=r.base_customers.iat[-1]))
    t = pd.DataFrame(tot)
    return t.quantile([0.1, 0.5, 0.9]).T.rename(columns={0.1: "p10", 0.5: "p50", 0.9: "p90"})


EXAMPLES = [
    Scenario("baseline"),
    Scenario("Fix app payments (+3% conversion)", conversion_pct=3),
    Scenario("Stop deep-discount acquisition", discount_pp=-1.5, cac_pct=15, conversion_pct=-1.0, refund_pp=-0.5),
    Scenario("Retention programme (-1pp monthly churn, +10% marketing)", retention_pp=1.0, marketing_pct=10),
    Scenario("Price +3% (assume -2% conversion)", aov_pct=3, conversion_pct=-2),
]


def summarise(b, scenarios):
    base_tot = project(b, Scenario()).sum(numeric_only=True)
    rows = []
    for s in scenarios:
        r = project(b, s)
        tot = r.sum(numeric_only=True)
        mc = monte_carlo(b, s, n=300)
        rows.append(dict(scenario=s.name, value_type="forecast" if s.name == "baseline" else "estimate",
                         net_revenue_12m=tot.net_revenue, cm_12m=tot.contribution_margin,
                         cm_after_mkt_12m=tot.cm_after_marketing, end_customers=r.base_customers.iat[-1],
                         ltv_cm=r.ltv_cm.mean(), ltv_to_cac=r.ltv_to_cac.mean(),
                         delta_cm_after_mkt_vs_base=tot.cm_after_marketing - base_tot.cm_after_marketing,
                         cm_after_mkt_p10=mc.loc["cm_after_marketing", "p10"],
                         cm_after_mkt_p90=mc.loc["cm_after_marketing", "p90"]))
    return pd.DataFrame(rows)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--example", action="store_true")
    for k in ["retention-pp", "conversion-pct", "aov-pct", "cac-pct", "refund-pp", "discount-pp", "marketing-pct"]:
        ap.add_argument(f"--{k}", type=float, default=0.0)
    a = ap.parse_args(argv)
    b = observed_baseline()
    params = pd.DataFrame([dict(parameter=k, value=v, value_type="observed", source="H2 2025 governed metrics")
                           for k, v in asdict(b).items() if k != "sd"])
    write_df(params, "scenario_baseline")
    scen = EXAMPLES if a.example else [Scenario(), Scenario("custom", a.retention_pp, a.conversion_pct, a.aov_pct,
                                                               a.cac_pct, a.refund_pp, a.discount_pp, a.marketing_pct)]
    summ = summarise(b, scen)
    proj = pd.concat([project(b, s).assign(scenario=s.name, value_type="forecast" if s.name == "baseline" else "estimate")
                      for s in scen])
    write_df(summ, "scenario_summary")
    write_df(proj, "scenario_projection")
    assumptions = pd.DataFrame([asdict(s) for s in scen])
    txt = f"""# Decision Simulator: example scenarios (12 months ahead)

## Observed baseline parameters (H2 2025, from governed metrics). Label: OBSERVED
{md_table(params[['parameter', 'value']])}

## Scenario assumptions. Label: ASSUMPTION (set by a human, not measured)
{md_table(assumptions)}

## Results. Labels: baseline = FORECAST, scenarios = ESTIMATE
{md_table(summ)}

P10/P90 come from 300 Monte-Carlo draws of the observed month-to-month variability of the inputs. They
capture parameter noise, **not** model error. The true uncertainty is wider.

### How to read this
* The ranking of scenarios by `delta_cm_after_mkt_vs_base` is the output. The absolute rupee values are
  only as good as the assumptions.
* "Stop deep-discount acquisition" only helps under the stated assumption about lost conversion. Change
  that assumption, and the answer can flip. Say this out loud in the meeting.
* None of these numbers are results. Report them as "if X, we estimate Y".
"""
    write("decision_simulator.md", txt)
    print(summ[["scenario", "net_revenue_12m", "cm_after_mkt_12m", "delta_cm_after_mkt_vs_base"]].round(0).to_string())


if __name__ == "__main__":
    main()
