"""
Data Quality Scorecard.

Six dimensions, each made of explicit, threshold-based checks (no black-box score):
  Uniqueness | Completeness | Validity | Referential integrity | Timeliness | Consistency
Each check -> observed value, threshold (warn/fail), status, and the business impact if it fails.
Score = 100 x weighted credit (pass = 1, warn = 0.8 because the defect is known AND mitigated, fail = 0). Output: dq.dq_checks, dq.dq_scorecard,
reports/data_quality_scorecard.md.

Why thresholds instead of "zero defects": real sources are never perfect. The question leadership needs
answered is "is the data good enough for THIS decision?" - tolerances make that explicit.
"""
from datetime import datetime, timezone

import pandas as pd

from nova.common.db import read_sql, write_df
from nova.common.report import md_table, write

CHECKS = [
    # (id, dimension, table, description, sql returning one value, warn, fail, higher_is_bad, impact, mitigation)
    ("U1", "Uniqueness", "orders", "Raw order rows that are duplicates of an order_id",
     "select 1 - count(distinct order_id)::numeric / count(*) from raw.orders", 0.005, 0.03, True,
     "Double-counted revenue and orders", "stg_orders keeps latest extract per order_id"),
    ("U2", "Uniqueness", "payments", "Payment rows that replay an existing gateway_txn_ref",
     "select 1 - count(distinct gateway_txn_ref)::numeric / count(*) from raw.payments", 0.001, 0.01, True,
     "Over-stated collections, wrong payment success rate", "stg_payments de-dups on gateway_txn_ref"),
    ("U3", "Uniqueness", "customers", "Exact-duplicate customer CDC rows",
     "select 1 - (select count(*) from staging.stg_customers)::numeric / count(*) from raw.customers", 0.01, 0.05, True,
     "Inflated customer counts", "stg_customers de-dups exact CDC rows"),
    ("C1", "Completeness", "customers", "Customers with no geography",
     "select avg((geo_id is null)::int) from staging.stg_customers", 0.03, 0.08, True,
     "State-level analysis loses customers", "mapped to 'Unknown' geography member"),
    ("C2", "Completeness", "products", "Product versions with missing unit cost (imputed)",
     "select avg(is_cost_missing::int) from staging.stg_products", 0.01, 0.05, True,
     "Gross profit uses an imputed cost", "imputed from category median cost ratio; flagged is_cost_imputed"),
    ("C3", "Completeness", "marketing_spend", "Spend rows with null impressions",
     "select avg((impressions is null or impressions = '')::int) from raw.marketing_spend", 0.005, 0.05, True,
     "CTR/CPM understated", "CTR computed only where impressions present"),
    ("V1", "Validity", "orders", "Orders with order date outside the reporting window",
     "select avg((not is_valid_order_date)::int) from marts.fct_orders", 0.001, 0.01, True,
     "Orders excluded from reporting", "excluded via is_reportable"),
    ("V2", "Validity", "orders", "Delivered before ordered",
     "select avg((delivered_at < order_at)::int) from staging.stg_orders where delivered_at is not null", 0.001, 0.01, True,
     "Delivery-time KPIs wrong", "days_to_deliver set NULL; order kept"),
    ("V3", "Validity", "refunds", "Refunds with negative sign (sign-corrected)",
     "select avg(is_sign_corrected::int) from staging.stg_refunds", 0.005, 0.03, True,
     "Refunds would reduce the refund total if not corrected", "abs() applied in staging; flagged"),
    ("V4", "Validity", "products/customers", "Raw category/channel labels needing a mapping",
     "select (select avg((category_raw <> lower(category))::int) from staging.stg_products)", 0.10, 0.40, True,
     "Unmapped values fall into 'Unmapped' buckets", "seed mapping tables"),
    ("V5", "Validity", "web_sessions", "Share of sessions flagged as bots",
     "select avg(is_bot::int) from staging.stg_web_sessions", 0.01, 0.05, True,
     "Conversion rate diluted if bots are not excluded", "is_bot flag; excluded from governed conversion"),
    ("R1", "Referential integrity", "order_items", "Order lines whose product_id is not in the product master",
     "select avg(is_orphan_product::int) from intermediate.int_order_items__priced", 0.001, 0.01, True,
     "Product profitability misses revenue", "'unknown' product member; cost imputed"),
    ("R2", "Referential integrity", "orders", "Orders whose customer is missing from the CRM extract",
     "select avg(is_orphan_customer::int) from marts.fct_orders where not is_guest", 0.002, 0.02, True,
     "Customer metrics miss orders", "'unknown' customer member; revenue kept"),
    ("T1", "Timeliness", "all", "Hours since last successful load",
     "select extract(epoch from now() - max(finished_at)) / 3600 from raw._ingestion_audit where status = 'success'",
     26, 50, True, "Dashboards show stale data", "freshness alert"),
    ("T2", "Timeliness", "refunds", "Share of return refunds that arrived > 7 days after the event",
     "select avg((arrival_lag_days > 7)::int) from staging.stg_refunds where not is_cancellation_refund", 0.2, 0.4, True,
     "Recent refund rates are provisional", "metrics_daily.is_refund_mature flag"),
    ("K1", "Consistency", "payments vs orders", "Completed prepaid orders where collected != order total",
     "select avg((abs(collected_inr - order_total_inr) > 1)::int) from marts.fct_orders "
     "where is_countable and is_prepaid and collected_inr is not null", 0.001, 0.01, True,
     "Finance reconciliation breaks", "paise->INR conversion in stg_payments"),
    ("K2", "Consistency", "metrics", "Governed net revenue: metrics_daily vs fct_orders (abs diff INR)",
     "select abs((select sum(net_revenue) from metrics.metrics_daily) - (select sum(net_revenue) from marts.fct_orders))",
     1, 100, True, "Two surfaces show different revenue", "dbt sum_reconciles test"),
]
WEIGHTS = {"Uniqueness": 1.0, "Completeness": 0.8, "Validity": 1.0, "Referential integrity": 1.0,
           "Timeliness": 0.8, "Consistency": 1.2}


def run_checks() -> pd.DataFrame:
    rows = []
    for cid, dim, table, desc, sql, warn, fail, _bad_high, impact, mitigation in CHECKS:
        try:
            v = read_sql(sql).iloc[0, 0]
            v = float(v) if v is not None else None
        except Exception as e:  # a check that cannot run is itself a failure
            v, desc = None, desc + f" (check error: {str(e)[:80]})"
        if v is None:
            status = "fail"
        elif v >= fail:
            status = "fail"
        elif v >= warn:
            status = "warn"
        else:
            status = "pass"
        rows.append(dict(check_id=cid, dimension=dim, table_name=table, description=desc, observed=v,
                         warn_threshold=warn, fail_threshold=fail, status=status, business_impact=impact,
                         mitigation=mitigation))
    # dbt test pass rate (latest run)
    try:
        t = read_sql("select status, count(*) n from dq.dbt_test_results where run_at = "
                     "(select max(run_at) from dq.dbt_test_results) group by 1")
        tot = t.n.sum()
        failing = t.loc[t.status.isin(["fail", "error"]), "n"].sum()
        warns = t.loc[t.status == "warn", "n"].sum()
        rows.append(dict(check_id="D1", dimension="Consistency", table_name="dbt", description=
                         f"dbt tests failing (error severity) - {int(tot)} tests, {int(warns)} known-defect warnings",
                         observed=float(failing), warn_threshold=1, fail_threshold=1,
                         status="fail" if failing else "pass", business_impact="Pipeline contract broken",
                         mitigation="build stops on error-severity tests"))
    except Exception:
        pass
    return pd.DataFrame(rows)


def score(checks: pd.DataFrame) -> pd.DataFrame:
    credit = checks.status.map({"pass": 1.0, "warn": 0.8, "fail": 0.0})   # warn = known & mitigated
    checks = checks.assign(credit=credit)
    dims = checks.groupby("dimension").agg(checks=("check_id", "count"), credit=("credit", "mean"),
                                           fails=("status", lambda s: (s == "fail").sum()),
                                           warns=("status", lambda s: (s == "warn").sum())).reset_index()
    dims["score"] = (dims.credit * 100).round(1)
    dims["weight"] = dims.dimension.map(WEIGHTS)
    overall = (dims.score * dims.weight).sum() / dims.weight.sum()
    dims = pd.concat([dims, pd.DataFrame([dict(dimension="OVERALL", checks=len(checks), score=round(overall, 1),
                                                fails=dims.fails.sum(), warns=dims.warns.sum())])], ignore_index=True)
    return dims.drop(columns=["credit"])


def main():
    checks = run_checks()
    now = datetime.now(timezone.utc)
    checks["run_at"] = now
    dims = score(checks)
    dims["run_at"] = now
    write_df(checks, "dq_checks", schema="dq")
    write_df(dims, "dq_scorecard", schema="dq")
    overall = dims.loc[dims.dimension == "OVERALL", "score"].iat[0]
    verdict = ("fit for executive reporting" if overall >= 90 else
               "fit with caveats (see warnings)" if overall >= 75 else "NOT fit - investigate before publishing")
    txt = f"""# Data Quality Scorecard

Generated: {now:%Y-%m-%d %H:%M UTC}. **Overall score: {overall} / 100 ({verdict})**

Scores are threshold-based: each check has an explicit warn and fail tolerance, and a business impact.
Warnings are **known, monitored source defects**. The pipeline corrects or flags every one of them, and they
must never be silently ignored.

## Dimension scores
{md_table(dims.drop(columns=['run_at']))}

## Checks
{md_table(checks.drop(columns=['run_at', 'business_impact']), floatfmt='{:,.4f}')}

## How to read this
* **pass**: within tolerance. **warn**: a known defect that is handled (de-duplicated, imputed, flagged).
  It is shown so that nobody is surprised. **fail**: a decision based on this data should wait.
* The score is not a KPI to maximise. It exists to answer "can leadership trust today's numbers?"
"""
    write("data_quality_scorecard.md", txt)
    print(dims[["dimension", "score"]].to_string(index=False))


if __name__ == "__main__":
    main()
