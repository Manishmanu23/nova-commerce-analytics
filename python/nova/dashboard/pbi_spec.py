"""
Single spec of what the Power BI dataset contains. Used by:
  * export_powerbi_data.py  -> powerbi/data/<table>.csv + schema.json
  * (planned) build_pbip.py -> powerbi/NovaCommerce.SemanticModel (tables, types, relationships, measures)
Only governed/aggregated tables are exported (no raw data, no PII, no 1.7M-row session fact).
"""
TABLES = {
    # ---------------- dimensions
    "dim_date": "select date_key, date_day, year, quarter, month, month_label, month_start, week_start, day_name, "
                "is_weekend, fiscal_year, festival_name, is_sale_period from marts.dim_date where is_in_reporting_window",
    "dim_customer": "select customer_version_key, customer_id, city, state, region, city_tier, acquisition_channel, "
                    "signup_campaign_id, is_legacy_customer, acquisition_cohort_month, is_current from marts.dim_customer",
    "dim_product": "select product_version_key, product_id, product_name, category, subcategory, brand, list_price, "
                   "unit_cost, is_current from marts.dim_product",
    "dim_geography": "select geo_id, city, state, region, city_tier from marts.dim_geography",
    "dim_channel": "select channel, channel_name, channel_group, is_paid from marts.dim_channel",
    "dim_campaign": "select campaign_id, campaign_name, channel as campaign_channel, objective, first_order_discount_pct, "
                    "start_date, end_date, is_deep_discount from marts.dim_campaign",
    "dim_device": "select device_type, platform from marts.dim_device",
    "dim_payment_method": "select payment_method, is_prepaid from marts.dim_payment_method",
    # ---------------- facts
    "fct_orders": "select order_id, order_date, geo_id, customer_version_key, attributed_channel, campaign_id, device_type, "
                  "payment_method, order_channel, customer_type, is_countable, is_first_order, is_member_order, "
                  "is_bulk_order, completed_orders, gross_revenue, coupon_discount, return_refunds, net_revenue, "
                  "net_cogs, gross_profit, shipping_fee_collected, variable_fulfilment_cost, contribution_margin, "
                  "aov_orders, aov_order_value, days_to_deliver from marts.fct_orders where is_valid_order_date",
    "fct_order_items": "select order_item_id, order_date, geo_id, attributed_channel, product_version_key, category, "
                       "brand, is_countable, is_refunded, refund_reason, units, gross_revenue, markdown, allocated_coupon, "
                       "return_refunds, net_revenue, net_cogs, gross_profit from marts.fct_order_items "
                       "where order_date between '2024-01-01' and '2025-12-31'",
    "fct_payments": "select payment_id, payment_date, payment_method, device_type, coalesce(app_version, 'n/a') as app_version, "
                    "geo_id, is_prepaid_attempt, is_success, failure_reason from marts.fct_payments "
                    "where is_reportable and payment_date between '2024-01-01' and '2025-12-31'",
    "fct_marketing_spend": "select spend_date, campaign_id, channel, is_acquisition_spend, spend_inr, impressions, clicks "
                           "from marts.fct_marketing_spend",
    "fct_refunds": "select refund_id, refund_date, order_date, refund_amount_inr, refund_reason, refund_status, "
                   "is_return_refund, category, brand, arrival_lag_days from marts.fct_refunds "
                   "where order_date between '2024-01-01' and '2025-12-31'",
    # ---------------- marts & metrics
    "mart_funnel_daily": "select * from marts.mart_funnel_daily",
    "mart_cohort_retention": "select * from marts.mart_cohort_retention",
    "mart_channel_monthly_economics": "select * from marts.mart_channel_monthly_economics",
    "mart_customer_ltv": "select customer_id, acquisition_channel, acquisition_channel as ltv_channel, is_deep_discount_acquired, "
                         "cohort_month, first_order_channel, first_order_campaign_id, total_orders, total_net_revenue, "
                         "total_cm, cm_90d, cm_180d, is_mature_90d, is_mature_180d, repeated_within_90d, "
                         "is_member_ever, days_since_last_order from marts.mart_customer_ltv",
    "metrics_daily": "select * from metrics.metrics_daily",
    "metrics_monthly": "select * from metrics.metrics_monthly",
    "metric_catalog": "select metric_name, display_name, owner, unit, definition from metrics.metric_catalog",
    # ---------------- quality, anomalies, analytics
    "dq_scorecard": "select dimension, checks, fails, warns, score from dq.dq_scorecard",
    "dbt_test_results": "select run_at, test_name, test_type, model, column_name, severity, status, failures "
                        "from dq.dbt_test_results",
    "dq_checks": "select check_id, dimension, table_name, description, observed, warn_threshold, fail_threshold, status, "
                 "mitigation from dq.dq_checks",
    "anomaly_alerts": "select metric, display, start_date, end_date, expected, actual, deviation, severity, classification, "
                      "evidence_note, est_impact_inr from analytics.anomaly_alerts",
    "anomaly_segment_alerts": "select * from analytics.anomaly_segment_alerts",
    "anomaly_segment_drilldown": "select * from analytics.anomaly_segment_drilldown",
    "customer_segments": "select customer_id, segment, recency_days, frequency, monetary_cm, r, f, m from analytics.customer_segments",
    "experiment_results": "select experiment_id, experiment_name, n_treatment, n_control, srm_p, cr_control, cr_treatment, "
                          "rel_lift, rel_ci_low, rel_ci_high, p_value, power_at_mde, decision from analytics.experiment_results",
    "scenario_baseline": "select parameter, value, value_type from analytics.scenario_baseline",
    "scenario_summary": "select * from analytics.scenario_summary",
    "revenue_forecast": "select week, value_type, p10, p50, p90, model from analytics.revenue_forecast",
}

# (from_table, from_column, to_table, to_column)  - many-to-one, single direction, NO fact-to-fact paths
RELATIONSHIPS = [
    ("fct_orders", "order_date", "dim_date", "date_day"),
    ("fct_order_items", "order_date", "dim_date", "date_day"),
    ("fct_payments", "payment_date", "dim_date", "date_day"),
    ("fct_marketing_spend", "spend_date", "dim_date", "date_day"),
    ("fct_refunds", "order_date", "dim_date", "date_day"),
    ("metrics_daily", "date_day", "dim_date", "date_day"),
    ("mart_funnel_daily", "date_day", "dim_date", "date_day"),
    ("fct_orders", "customer_version_key", "dim_customer", "customer_version_key"),
    ("fct_orders", "geo_id", "dim_geography", "geo_id"),
    ("fct_order_items", "geo_id", "dim_geography", "geo_id"),
    ("fct_payments", "geo_id", "dim_geography", "geo_id"),
    ("fct_orders", "attributed_channel", "dim_channel", "channel"),
    ("fct_order_items", "attributed_channel", "dim_channel", "channel"),
    ("fct_marketing_spend", "channel", "dim_channel", "channel"),
    ("mart_channel_monthly_economics", "channel", "dim_channel", "channel"),
    ("fct_orders", "campaign_id", "dim_campaign", "campaign_id"),
    ("fct_marketing_spend", "campaign_id", "dim_campaign", "campaign_id"),
    ("fct_order_items", "product_version_key", "dim_product", "product_version_key"),
    ("fct_orders", "device_type", "dim_device", "device_type"),
    ("fct_payments", "device_type", "dim_device", "device_type"),
    ("mart_funnel_daily", "device_type", "dim_device", "device_type"),
]
