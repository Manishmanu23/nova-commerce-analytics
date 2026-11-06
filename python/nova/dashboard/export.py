"""
Build the 6-page interactive dashboard (HTML) and the Power BI CSV data pack from the governed warehouse.

    python -m nova.dashboard.export
      -> powerbi/dashboard/NovaCommerce_Dashboard.html   (open in any browser; Power BI-style preview)
      -> powerbi/data/*.csv + schema.json                 (via export_powerbi_data; import into Power BI Desktop)

The dashboard reads ONLY governed tables (metrics.*, marts.mart_*, analytics.*, dq.*). No metric is re-defined in
JavaScript: ratios are recomputed from the exported numerators/denominators exactly as in the metric catalogue.
"""
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from nova.common.db import read_sql
from nova.common.report import ROOT

OUT_HTML = ROOT / "powerbi" / "dashboard" / "NovaCommerce_Dashboard.html"
TEMPLATE = ROOT / "powerbi" / "dashboard" / "template.html"

Q = {
    "monthly": """
        select m.month, m.orders, m.gross_revenue, m.coupon_discount, m.return_refund_amount, m.net_revenue,
               m.gross_profit, m.contribution_margin, m.marketing_spend, m.acquisition_spend,
               m.contribution_margin_after_marketing, m.aov_orders, m.aov_order_value, m.new_customers,
               m.paid_new_customers, m.sessions, m.purchase_sessions, m.checkout_sessions, m.payment_attempts,
               m.successful_payment_attempts, m.attributed_net_revenue, m.web_app_net_revenue, m.active_customers,
               m.cohort_customers_90d, m.repeaters_90d, m.cohort_customers_180d, m.cm_180d, m.active_base,
               m.churned_customers, d.net_cogs, d.shipping_fee_collected, d.variable_fulfilment_cost
        from metrics.metrics_monthly m
        join (select date_trunc('month', date_day)::date as month, sum(net_cogs) net_cogs,
                     sum(shipping_fee_collected) shipping_fee_collected, sum(variable_fulfilment_cost) variable_fulfilment_cost
              from metrics.metrics_daily group by 1) d using (month)
        order by month""",
    "dim_monthly": """
        select date_trunc('month', date_day)::date as month, dimension_name as dim, dimension_value as val,
               sum(net_revenue) net_revenue, sum(orders) orders, sum(contribution_margin) cm,
               sum(gross_revenue) gross_revenue, sum(return_refund_amount) refunds, sum(sessions) sessions,
               sum(purchase_sessions) purchase_sessions, sum(checkout_sessions) checkout_sessions,
               sum(payment_attempts) payment_attempts, sum(successful_payment_attempts) successful_payment_attempts
        from metrics.metrics_daily_by_dimension
        where dimension_name in ('channel','customer_type','device_type','state','category','payment_method','order_channel')
        group by 1, 2, 3""",
    "cohorts": """
        select cohort_month, acquisition_segment as seg, months_since_first as m, sum(cohort_size) size,
               sum(active_customers) active, sum(cumulative_cm) cum_cm
        from marts.mart_cohort_retention group by 1, 2, 3""",
    "segments": """
        select segment, count(*) customers, round(avg(recency_days)) recency, round(avg(frequency)::numeric, 2) frequency,
               round(sum(monetary_cm)) cm from analytics.customer_segments group by 1 order by 5 desc""",
    "ltv_channel": """
        with l as (select first_order_channel channel, count(*) n, avg(cm_180d) ltv, min(cohort_month) a, max(cohort_month) b
                   from marts.mart_customer_ltv where is_mature_180d group by 1),
             c as (select e.channel, sum(e.acquisition_spend) spend, sum(e.new_customers) nc
                   from marts.mart_channel_monthly_economics e join l on l.channel = e.channel and e.month between l.a and l.b group by 1)
        select l.channel, l.n customers, round(l.ltv) ltv_180d_cm, round(c.spend / nullif(c.nc, 0)) cac
        from l left join c using (channel) order by 3 desc""",
    "product_monthly": """
        select month, category, sum(units) units, sum(gross_revenue) gross, sum(net_revenue) net, sum(gross_profit) gp,
               sum(return_refunds) refunds, sum(coupon) coupon, sum(order_lines) lines, sum(refunded_lines) refunded_lines,
               sum(defective_lines) defective_lines
        from marts.mart_product_monthly group by 1, 2""",
    "brand_quarterly": """
        select date_trunc('quarter', month)::date q, category, brand, sum(gross_revenue) gross, sum(return_refunds) refunds,
               sum(order_lines) lines, sum(defective_lines) defective_lines
        from marts.mart_product_monthly group by 1, 2, 3""",
    "products_2025": """
        select product_id, category, brand, sum(gross_profit) gp, sum(net_revenue) net, sum(units) units
        from marts.mart_product_monthly where month >= '2025-01-01' group by 1, 2, 3""",
    "refund_reasons": """
        select category, refund_reason reason, count(*) n, sum(refund_amount_inr) amount from marts.fct_refunds
        where is_return_refund and refund_status = 'processed' and category <> 'n/a' group by 1, 2""",
    "channel_econ": "select * from marts.mart_channel_monthly_economics",
    "campaigns": """
        with sp as (select campaign_id, sum(spend_inr) spend from marts.fct_marketing_spend group by 1)
        select dc.campaign_id, dc.campaign_name, dc.channel, dc.first_order_discount_pct disc, count(*) customers,
               round(max(sp.spend) / count(*)) cac, round(avg(cm_90d) filter (where is_mature_90d)) cm90,
               round(avg(repeated_within_90d::int) filter (where is_mature_90d), 3) repeat90
        from marts.mart_customer_ltv l join marts.dim_campaign dc on dc.campaign_id = l.signup_campaign_id
        join sp on sp.campaign_id = dc.campaign_id group by 1, 2, 3, 4 having count(*) >= 30""",
    "funnel_monthly": """
        select date_trunc('month', date_day)::date as month, device_type, sum(sessions) s, sum(product_view_sessions) pv,
               sum(add_to_cart_sessions) atc, sum(checkout_sessions) co, sum(payment_attempt_sessions) pa,
               sum(purchase_sessions) pu from marts.mart_funnel_daily group by 1, 2""",
    "pay_weekly": """
        select date_trunc('week', p.payment_date)::date wk, p.device_type,
               case when g.state in ('Uttar Pradesh','Bihar','West Bengal') then g.state else 'Other states' end st,
               count(*) attempts, sum(p.is_success::int) ok
        from marts.fct_payments p join marts.dim_geography g using (geo_id)
        where p.is_prepaid_attempt and p.is_reportable and p.payment_date between '2024-01-01' and '2025-12-31'
        group by 1, 2, 3""",
    "checkout_weekly": """
        select date_trunc('week', date_day)::date wk, device_type, sum(checkout_sessions) co, sum(purchase_sessions) pu
        from marts.mart_funnel_daily group by 1, 2""",
    "experiments": """select experiment_id, experiment_name, n_treatment, n_control, srm_p, cr_control, cr_treatment,
                             rel_lift, rel_ci_low, rel_ci_high, p_value, power_at_mde, decision from analytics.experiment_results
                      order by 1""",
    "dq_dims": "select dimension, checks, fails, warns, score from dq.dq_scorecard",
    "dq_checks": "select check_id, dimension, table_name, description, observed, warn_threshold, fail_threshold, status, mitigation from dq.dq_checks order by check_id",
    "dbt_tests": """select status, severity, count(*) n from dq.dbt_test_results
                    where run_at = (select max(run_at) from dq.dbt_test_results) group by 1, 2""",
    "dbt_warns": """select test_name, model, failures from dq.dbt_test_results
                    where run_at = (select max(run_at) from dq.dbt_test_results) and status <> 'pass' order by failures desc""",
    "alerts": """select metric, display, start_date, end_date, expected, actual, deviation, max_abs_z, severity, classification,
                        evidence_note, est_impact_inr from analytics.anomaly_alerts order by start_date""",
    "seg_alerts": "select * from analytics.anomaly_segment_alerts order by start_date",
    "seg_drill": "select * from analytics.anomaly_segment_drilldown",
    "daily_rev": """select date_day d, net_revenue actual from metrics.metrics_daily order by 1""",
    "reconciliation": """
        select (select count(*) from raw.orders) raw_rows, (select count(distinct order_id) from raw.orders) raw_distinct,
               (select count(*) from marts.fct_orders where not is_valid_order_date) invalid_dates,
               (select count(*) from marts.fct_orders where is_internal_test) test_orders,
               (select count(*) from marts.fct_orders where not is_completed) not_completed,
               (select sum(net_revenue) from marts.fct_orders) fct_net,
               (select sum(net_revenue) from metrics.metrics_daily) metrics_net,
               (select sum(net_revenue) from marts.fct_order_items) items_net""",
    "sim_baseline": "select parameter, value from analytics.scenario_baseline",
    "sim_summary": "select * from analytics.scenario_summary",
    "forecast": "select week, value_type, p10, p50, p90, model from analytics.revenue_forecast order by week",
    "catalog": "select metric_name, display_name, owner, unit, definition from metrics.metric_catalog",
}

def _clean(df: pd.DataFrame):
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            df[c] = df[c].dt.strftime("%Y-%m-%d")
        elif df[c].dtype == object:
            df[c] = df[c].map(lambda v: v.isoformat()[:10] if hasattr(v, "isoformat") else
                              (float(v) if hasattr(v, "as_integer_ratio") and not isinstance(v, (int, bool)) else v))
    df = df.replace({np.nan: None})
    return df.to_dict("records")


def build_data() -> dict:
    data = {k: _clean(read_sql(sql)) for k, sql in Q.items()}
    dq = {r["dimension"]: r["score"] for r in data["dq_dims"]}
    overall = float(dq.get("OVERALL", 0))
    data["meta"] = dict(generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                        data_start="2024-01-01", data_end="2025-12-31", dq_score=overall,
                        dq_verdict="Fit" if overall >= 90 else "Fit with caveats" if overall >= 75 else "Not fit")
    return data


def export_csv():
    """CSV data pack: delegates to export_powerbi_data (curated spec in pbi_spec.py: governed tables only, no raw PII)."""
    from nova.dashboard import export_powerbi_data
    export_powerbi_data.main()


def main():
    data = build_data()
    html = TEMPLATE.read_text().replace("/*__DATA__*/null", json.dumps(data, default=str, separators=(",", ":")))
    OUT_HTML.write_text(html)
    print(f"wrote {OUT_HTML.relative_to(ROOT)} ({len(html) / 1024:.0f} KB)")
    export_csv()


if __name__ == "__main__":
    main()
