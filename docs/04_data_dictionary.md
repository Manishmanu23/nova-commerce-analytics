# Data Dictionary

Generated from the warehouse (`information_schema`) plus dbt model YAML, by `python -m nova.common.data_dictionary`. Grain statements are in the first line of each model.

## `marts.dim_campaign`

grain: one row per campaign

| column | type | description |
|---|---|---|
| campaign_id | text | FK to dim_campaign; attributed campaign (session UTM, else signup campaign on first order). |
| campaign_name | text |  |
| channel | text |  |
| channel_name | text |  |
| objective | text |  |
| first_order_discount_pct | numeric |  |
| start_date | date |  |
| end_date | date |  |
| duration_days | integer |  |
| is_deep_discount | boolean |  |

## `marts.dim_channel`

Conformed channel dimension shared by orders, sessions and spend.

| column | type | description |
|---|---|---|
| channel | text |  |
| channel_name | text |  |
| channel_group | text |  |
| is_paid | boolean |  |
| is_acquisition_channel | boolean |  |

## `marts.dim_customer`

Customer dimension, SCD Type 2. Grain: one row per customer version. 'unknown' member for guests/orphans.

| column | type | description |
|---|---|---|
| customer_version_key | text | Surrogate key = md5(customer_id, updated_at). Facts join on this for as-of attributes. |
| customer_id | text | Natural key of the customer (CRM). NULL = guest checkout. |
| email_hash | text | md5 of normalised email. Raw email never leaves staging (PII minimisation). |
| signup_at | timestamp without time zone |  |
| signup_date | date |  |
| geo_id | text | FK to dim_geography ('-1' = Unknown). |
| city | text |  |
| state | text |  |
| region | text |  |
| city_tier | integer |  |
| acquisition_channel | text |  |
| signup_campaign_id | text |  |
| is_marketing_opt_in | boolean |  |
| is_internal_test | boolean |  |
| is_legacy_customer | boolean | Signed up before 2024; pre-2024 history not migrated, excluded from cohort/LTV analysis. |
| first_order_date | date |  |
| acquisition_cohort_month | date | Month of first completed reportable order (NOT signup month). |
| is_buyer | boolean |  |
| version_number | bigint |  |
| valid_from | timestamp without time zone | Inclusive start of version validity (first version = 1900-01-01). |
| valid_to | timestamp without time zone | Exclusive end of version validity (current = 9999-12-31). |
| is_current | boolean | TRUE for the current SCD2 version. |

## `marts.dim_date`

Calendar dimension. Grain: one row per date. Indian fiscal year (Apr-Mar) and festival flags.

| column | type | description |
|---|---|---|
| date_key | integer | Surrogate key YYYYMMDD. |
| date_day | date | Calendar date (IST). |
| year | integer |  |
| quarter | integer |  |
| month | integer | First day of the month. |
| month_label | text |  |
| month_start | date |  |
| week_start | date |  |
| iso_day_of_week | integer |  |
| day_name | text |  |
| is_weekend | boolean |  |
| fiscal_year | text |  |
| fiscal_quarter | text |  |
| festival_name | text |  |
| is_sale_period | boolean |  |
| is_in_reporting_window | boolean |  |

## `marts.dim_device`



| column | type | description |
|---|---|---|
| device_type | text | mobile_app | mobile_web | desktop | unknown (marketplace). |
| platform | text |  |
| is_mobile | boolean |  |

## `marts.dim_experiment`



| column | type | description |
|---|---|---|
| experiment_id | text |  |
| experiment_name | text |  |
| hypothesis | text |  |
| primary_metric | text |  |
| randomisation_unit | text |  |
| planned_split | numeric |  |
| start_date | date |  |
| end_date | date |  |
| duration_days | integer |  |
| owner | text |  |
| status | text |  |

## `marts.dim_geography`

grain: one row per geo_id (+ an explicit Unknown member so fact FKs are never NULL)

| column | type | description |
|---|---|---|
| geo_id | text | FK to dim_geography ('-1' = Unknown). |
| city | text |  |
| state | text |  |
| region | text |  |
| city_tier | integer |  |

## `marts.dim_payment_method`



| column | type | description |
|---|---|---|
| payment_method | text | Standardised payment method (UPI, Card, COD, Wallet, EMI). |
| is_prepaid | boolean |  |

## `marts.dim_product`

Product dimension, SCD Type 2 (price and cost history). Grain: one row per product version.

| column | type | description |
|---|---|---|
| product_version_key | text | FK to dim_product version valid at order time (SCD2). |
| product_id | text | Natural key of the product. |
| sku | text |  |
| product_name | text |  |
| category | text |  |
| subcategory | text |  |
| brand | text |  |
| list_price | numeric |  |
| unit_cost | numeric | Landed unit cost valid for the version; imputed from category median ratio if missing (is_cost_imputed). |
| list_margin_pct | numeric |  |
| is_cost_imputed | boolean |  |
| version_number | bigint |  |
| valid_from | timestamp without time zone | SCD2 validity start (inclusive). |
| valid_to | timestamp without time zone | SCD2 validity end (exclusive). |
| is_current | boolean | TRUE for the current SCD2 version. |

## `marts.fct_customer_monthly`

Grain: ONE ROW PER (CUSTOMER, MONTH) from first-order month. Periodic snapshot.

| column | type | description |
|---|---|---|
| customer_id | text | Natural key of the customer (CRM). NULL = guest checkout. |
| cohort_month | date | Month of the customer's first completed order. |
| is_legacy_customer | boolean | Signed up before 2024; pre-2024 history not migrated, excluded from cohort/LTV analysis. |
| month | date | First day of the month. |
| months_since_first | integer | Months since the customer's first order month. |
| orders | bigint | Count of countable orders. |
| net_revenue | numeric | Governed: gross revenue - coupon discounts - processed return refunds. |
| contribution_margin | numeric | Governed: gross profit + shipping fees - shipping cost - payment fees - marketplace commission. |
| is_active | boolean | Customer placed >= 1 countable order in the month. |
| cumulative_net_revenue | numeric |  |
| cumulative_cm | numeric |  |

## `marts.fct_experiment_exposures`

Grain: ONE ROW PER (EXPERIMENT, CUSTOMER). Outcomes measured strictly after assignment.

| column | type | description |
|---|---|---|
| experiment_id | text |  |
| customer_id | text | Natural key of the customer (CRM). NULL = guest checkout. |
| variant | text |  |
| assigned_at | timestamp without time zone |  |
| platform | text |  |
| orders_in_window | bigint |  |
| converted | integer |  |
| net_revenue | numeric | Governed: gross revenue - coupon discounts - processed return refunds. |
| contribution_margin | numeric | Governed: gross profit + shipping fees - shipping cost - payment fees - marketplace commission. |
| shipping_fee_paid | numeric |  |
| pre_period_orders | bigint |  |
| pre_period_net_revenue | numeric |  |

## `marts.fct_funnel_steps`

Grain: ONE ROW PER (SESSION, FUNNEL STEP REACHED). Non-bot sessions only.

| column | type | description |
|---|---|---|
| session_id | bigint | Web/app session id (NULL for marketplace orders). |
| session_date | date |  |
| device_type | text | mobile_app | mobile_web | desktop | unknown (marketplace). |
| geo_id | text | FK to dim_geography ('-1' = Unknown). |
| traffic_channel | text |  |
| app_version | text |  |
| step_number | integer |  |
| step_name | text |  |

## `marts.fct_marketing_spend`

Grain: ONE ROW PER (DATE, CAMPAIGN). Net of credit notes.

| column | type | description |
|---|---|---|
| spend_date | date |  |
| spend_date_key | integer |  |
| campaign_id | text | FK to dim_campaign; attributed campaign (session UTM, else signup campaign on first order). |
| channel | text |  |
| objective | text |  |
| is_acquisition_spend | boolean |  |
| spend_inr | numeric |  |
| gross_spend_inr | numeric |  |
| credit_note_inr | numeric |  |
| impressions | numeric |  |
| clicks | numeric |  |
| null_impression_rows | bigint |  |

## `marts.fct_order_items`

Grain: ONE ROW PER ORDER LINE. Coupons allocated pro-rata to lines.

| column | type | description |
|---|---|---|
| order_item_id | text | Natural key of the order line. |
| order_id | text | Natural key of the order (OMS). |
| order_date | date | Order date in IST. |
| order_month | date | First day of the order month (IST). |
| customer_id | text | Natural key of the customer (CRM). NULL = guest checkout. |
| geo_id | text | FK to dim_geography ('-1' = Unknown). |
| attributed_channel | text | Standardised channel after attribution (dim_channel). |
| device_type | text | mobile_app | mobile_web | desktop | unknown (marketplace). |
| product_version_key | text | FK to dim_product version valid at order time (SCD2). |
| product_id | text | Natural key of the product. |
| category | text |  |
| subcategory | text |  |
| brand | text |  |
| is_orphan_product | boolean |  |
| is_cost_imputed | boolean |  |
| is_countable | boolean | TRUE when the order is completed AND reportable - governed measures are non-zero only then. |
| is_bulk_order | boolean | Any line with quantity >= 20 (B2B). Kept in revenue, excluded from AOV. |
| is_first_order | boolean | First completed order of a non-legacy customer (= new customer). |
| quantity | integer |  |
| unit_list_price | numeric |  |
| unit_sale_price | numeric |  |
| unit_cost | numeric |  |
| refund_reason | text |  |
| first_refund_at | timestamp without time zone |  |
| is_refunded | boolean |  |
| units | integer |  |
| list_value | numeric |  |
| markdown | numeric |  |
| gross_revenue | numeric | Governed: qty x selling price on countable orders (after markdowns, before coupons/refunds). |
| allocated_coupon | numeric |  |
| return_refunds | numeric | Processed return refunds on countable orders. |
| net_revenue | numeric | Governed: gross revenue - coupon discounts - processed return refunds. |
| net_cogs | numeric | COGS minus cost recovered on restockable returns. |
| gross_profit | numeric | Governed: net revenue - net COGS. |

## `marts.fct_orders`

Grain: ONE ROW PER ORDER (accumulating snapshot). Governed measures are pre-filtered: they are 0 unless is_countable (completed AND reportable), so SUM() always returns the governed value.

| column | type | description |
|---|---|---|
| order_id | text | Natural key of the order (OMS). |
| order_date_key | integer |  |
| order_date | date | Order date in IST. |
| order_at | timestamp without time zone | Order timestamp in IST (source is UTC). |
| order_month | date | First day of the order month (IST). |
| customer_id | text | Natural key of the customer (CRM). NULL = guest checkout. |
| customer_version_key | text | As-of customer version (SCD2 point-in-time join on order_at). |
| geo_id | text | FK to dim_geography ('-1' = Unknown). |
| attributed_channel | text | Last non-direct touch: session UTM campaign > signup campaign (first orders) > session channel > direct. |
| campaign_id | text | FK to dim_campaign; attributed campaign (session UTM, else signup campaign on first order). |
| session_id | bigint | Web/app session id (NULL for marketplace orders). |
| device_type | text | mobile_app | mobile_web | desktop | unknown (marketplace). |
| os | text |  |
| app_version | text |  |
| payment_method | text | Standardised payment method (UPI, Card, COD, Wallet, EMI). |
| is_prepaid | boolean |  |
| order_channel | text |  |
| source_system | text |  |
| order_status | text |  |
| coupon_code | text |  |
| is_completed | boolean | Order status in delivered/shipped/processing. |
| is_cancelled | boolean |  |
| is_payment_failed | boolean |  |
| is_reportable | boolean | Valid order date and not an internal test order. |
| is_countable | boolean | is_completed AND is_reportable (valid order date, not an internal test order). |
| is_valid_order_date | boolean |  |
| is_internal_test | boolean |  |
| is_guest | boolean |  |
| is_orphan_customer | boolean |  |
| is_legacy_customer | boolean | Signed up before 2024; pre-2024 history not migrated, excluded from cohort/LTV analysis. |
| is_bulk_order | boolean | Any line with quantity >= 20 (B2B). Kept in revenue, excluded from AOV. |
| is_member_order | boolean | Nova Plus membership active at order time. |
| is_first_order | boolean | First completed order of a non-legacy customer (= new customer). |
| customer_order_number | bigint |  |
| has_orphan_product | boolean |  |
| has_imputed_cost | boolean |  |
| source_row_count | bigint |  |
| customer_type | text |  |
| prepaid_attempts | bigint |  |
| failed_payment_attempts | bigint |  |
| success_attempt_no | integer |  |
| collected_inr | numeric |  |
| items_gross_revenue_inr | numeric |  |
| coupon_discount_inr | numeric |  |
| shipping_fee_inr | numeric |  |
| order_total_inr | numeric |  |
| shipping_cost_inr | numeric |  |
| marketplace_commission_inr | numeric |  |
| payment_fee_inr | numeric |  |
| return_refund_inr_raw | numeric |  |
| cancellation_refund_inr | numeric |  |
| cogs_inr_raw | numeric |  |
| cogs_recovered_inr_raw | numeric |  |
| completed_orders | integer | 1 if the order is countable, else 0. |
| gross_revenue | numeric | Governed: qty x selling price on countable orders (after markdowns, before coupons/refunds). |
| coupon_discount | numeric | Order-level coupon discount on countable orders. |
| return_refunds | numeric | Processed return refunds on countable orders. |
| net_revenue | numeric | Gross revenue - coupon discount - processed return refunds (governed). |
| net_cogs | numeric | COGS minus cost recovered on restockable returns. |
| gross_profit | numeric | Governed: net revenue - net COGS. |
| shipping_fee_collected | numeric |  |
| variable_fulfilment_cost | numeric |  |
| contribution_margin | numeric | Gross profit + shipping fee collected - shipping cost - payment fees - marketplace commission (governed, before marketing). |
| aov_orders | integer | AOV denominator: countable non-bulk orders. |
| aov_order_value | numeric | AOV numerator: gross - coupons on countable non-bulk orders. |
| shipped_at | timestamp without time zone |  |
| delivered_at | timestamp without time zone |  |
| cancelled_at | timestamp without time zone |  |
| hours_to_ship | numeric |  |
| days_to_deliver | numeric |  |

## `marts.fct_payments`

Grain: ONE ROW PER PAYMENT ATTEMPT.

| column | type | description |
|---|---|---|
| payment_id | text |  |
| order_id | text | Natural key of the order (OMS). |
| attempt_no | integer |  |
| payment_at | timestamp without time zone |  |
| payment_date | date |  |
| payment_date_key | integer |  |
| payment_method | text | Standardised payment method (UPI, Card, COD, Wallet, EMI). |
| gateway | text |  |
| is_prepaid_attempt | boolean |  |
| amount_inr | numeric |  |
| payment_status | text |  |
| is_success | boolean |  |
| failure_reason | text |  |
| gateway_fee_inr | numeric |  |
| device_type | text | mobile_app | mobile_web | desktop | unknown (marketplace). |
| app_version | text |  |
| order_channel | text |  |
| geo_id | text | FK to dim_geography ('-1' = Unknown). |
| is_reportable | boolean | Valid order date and not an internal test order. |

## `marts.fct_refunds`

Grain: ONE ROW PER REFUND TRANSACTION. Cancellation refunds are flagged and excluded from refund_rate.

| column | type | description |
|---|---|---|
| refund_id | text |  |
| order_id | text | Natural key of the order (OMS). |
| order_item_id | text | Natural key of the order line. |
| refund_at | timestamp without time zone |  |
| refund_date | date |  |
| order_date | date | Order date in IST. |
| refund_amount_inr | numeric |  |
| refund_reason | text |  |
| refund_status | text |  |
| is_cancellation_refund | boolean |  |
| is_return_refund | boolean |  |
| is_sign_corrected | boolean |  |
| batch_id | text |  |
| arrival_lag_days | numeric |  |
| days_after_delivery | numeric |  |
| product_id | text | Natural key of the product. |
| category | text |  |
| brand | text |  |
| attributed_channel | text | Standardised channel after attribution (dim_channel). |
| payment_method | text | Standardised payment method (UPI, Card, COD, Wallet, EMI). |
| geo_id | text | FK to dim_geography ('-1' = Unknown). |
| is_countable | boolean | TRUE when the order is completed AND reportable - governed measures are non-zero only then. |

## `marts.fct_sessions`

Grain: ONE ROW PER WEB/APP SESSION. Bots flagged (is_bot), not deleted.

| column | type | description |
|---|---|---|
| session_id | bigint | Web/app session id (NULL for marketplace orders). |
| session_date | date |  |
| session_date_key | integer |  |
| session_start_at | timestamp without time zone |  |
| customer_id | text | Natural key of the customer (CRM). NULL = guest checkout. |
| device_type | text | mobile_app | mobile_web | desktop | unknown (marketplace). |
| os | text |  |
| browser | text |  |
| app_version | text |  |
| geo_id | text | FK to dim_geography ('-1' = Unknown). |
| traffic_channel | text |  |
| campaign_id | text | FK to dim_campaign; attributed campaign (session UTM, else signup campaign on first order). |
| landing_page | text |  |
| duration_sec | integer |  |
| is_bot | boolean | Session flagged as bot traffic. |
| n_events | bigint |  |
| has_product_view | boolean |  |
| has_add_to_cart | boolean |  |
| has_begin_checkout | boolean |  |
| has_payment_attempt | boolean |  |
| has_purchase | boolean |  |
| n_payment_attempts | bigint |  |
| order_id | text | Natural key of the order (OMS). |

## `marts.fct_subscriptions`

grain: ONE ROW PER NOVA PLUS SUBSCRIPTION

| column | type | description |
|---|---|---|
| subscription_id | text |  |
| customer_id | text | Natural key of the customer (CRM). NULL = guest checkout. |
| plan_type | text |  |
| start_at | timestamp without time zone |  |
| end_at | timestamp without time zone |  |
| start_date | date |  |
| status | text |  |
| fee_inr | numeric |  |
| months_active | numeric |  |

## `marts.fct_support_tickets`

grain: ONE ROW PER SUPPORT TICKET

| column | type | description |
|---|---|---|
| ticket_id | text |  |
| customer_id | text | Natural key of the customer (CRM). NULL = guest checkout. |
| order_id | text | Natural key of the order (OMS). |
| created_at | timestamp without time zone |  |
| created_date | date |  |
| ticket_category | text |  |
| contact_channel | text |  |
| priority | text |  |
| resolved_at | timestamp without time zone |  |
| csat_score | integer |  |
| is_invalid_resolution | boolean |  |
| resolution_hours | numeric |  |
| device_type | text | mobile_app | mobile_web | desktop | unknown (marketplace). |
| payment_method | text | Standardised payment method (UPI, Card, COD, Wallet, EMI). |
| geo_id | text | FK to dim_geography ('-1' = Unknown). |

## `marts.mart_channel_monthly_economics`

Grain: (month, channel). Spend, CAC, ROAS, CM after marketing, LTV:CAC.

| column | type | description |
|---|---|---|
| month | date | First day of the month. |
| channel | text |  |
| marketing_spend | numeric | Net marketing spend (credit notes netted). |
| acquisition_spend | numeric | Net spend of acquisition-objective campaigns (excludes email/CRM). |
| orders | bigint | Count of countable orders. |
| new_customers | bigint | Customers whose first completed order falls in the period. |
| net_revenue | numeric | Governed: gross revenue - coupon discounts - processed return refunds. |
| contribution_margin | numeric | Governed: gross profit + shipping fees - shipping cost - payment fees - marketplace commission. |
| contribution_margin_after_marketing | numeric | Contribution margin minus net marketing spend (date/channel grain only). |
| campaign_attributed_net_revenue | numeric |  |
| cac | numeric | acquisition_spend / paid_new_customers. |
| roas | numeric | attributed net revenue / marketing spend. |
| mature_90d_customers | bigint |  |
| cm_90d | numeric |  |
| ltv_90d_cm | numeric |  |
| mature_180d_customers | bigint |  |
| cm_180d | numeric |  |
| ltv_180d_cm | numeric |  |
| ltv180_to_cac | numeric |  |

## `marts.mart_cohort_retention`

Grain: (cohort_month, acquisition_segment, months_since_first). Additive counts.

| column | type | description |
|---|---|---|
| cohort_month | date | Month of the customer's first completed order. |
| acquisition_channel | text |  |
| acquisition_segment | text |  |
| months_since_first | integer | Months since the customer's first order month. |
| cohort_size | bigint |  |
| active_customers | bigint |  |
| retention_rate | numeric |  |
| cumulative_net_revenue | numeric |  |
| cumulative_cm | numeric |  |

## `marts.mart_customer_ltv`

Grain: ONE ROW PER BUYING CUSTOMER. LTV windows with maturity flags.

| column | type | description |
|---|---|---|
| customer_id | text | Natural key of the customer (CRM). NULL = guest checkout. |
| acquisition_channel | text |  |
| signup_campaign_id | text |  |
| signup_campaign_discount | numeric |  |
| is_deep_discount_acquired | boolean |  |
| cohort_month | date | Month of the customer's first completed order. |
| state | text |  |
| city_tier | integer |  |
| first_order_date | date |  |
| first_order_channel | text |  |
| first_order_campaign_id | text |  |
| first_order_coupon | numeric |  |
| first_order_gross | numeric |  |
| total_orders | bigint |  |
| total_net_revenue | numeric |  |
| total_cm | numeric |  |
| last_order_date | date |  |
| is_member_ever | boolean |  |
| orders_90d | bigint |  |
| net_revenue_90d | numeric |  |
| cm_90d | numeric |  |
| orders_180d | bigint |  |
| net_revenue_180d | numeric |  |
| cm_180d | numeric |  |
| orders_365d | bigint |  |
| net_revenue_365d | numeric |  |
| cm_365d | numeric |  |
| days_observed | integer |  |
| is_mature_90d | boolean |  |
| is_mature_180d | boolean |  |
| is_mature_365d | boolean |  |
| repeated_within_90d | boolean |  |
| days_since_last_order | integer |  |
| is_churned_90d | boolean |  |

## `marts.mart_funnel_daily`

Grain: (date, device, state, traffic_channel, app_version). Non-bot sessions.

| column | type | description |
|---|---|---|
| date_day | date | Calendar date (IST). |
| device_type | text | mobile_app | mobile_web | desktop | unknown (marketplace). |
| state | text |  |
| traffic_channel | text |  |
| app_version | text |  |
| sessions | bigint | Non-bot web/app sessions. |
| product_view_sessions | bigint |  |
| add_to_cart_sessions | bigint |  |
| checkout_sessions | bigint | Non-bot sessions that began checkout. |
| payment_attempt_sessions | bigint |  |
| purchase_sessions | bigint | Non-bot sessions with a purchase event. |

## `marts.mart_product_monthly`

Grain: (month, product_id).

| column | type | description |
|---|---|---|
| month | date | First day of the month. |
| product_id | text | Natural key of the product. |
| category | text |  |
| subcategory | text |  |
| brand | text |  |
| units | bigint |  |
| gross_revenue | numeric | Governed: qty x selling price on countable orders (after markdowns, before coupons/refunds). |
| markdown | numeric |  |
| coupon | numeric |  |
| return_refunds | numeric | Processed return refunds on countable orders. |
| net_revenue | numeric | Governed: gross revenue - coupon discounts - processed return refunds. |
| net_cogs | numeric | COGS minus cost recovered on restockable returns. |
| gross_profit | numeric | Governed: net revenue - net COGS. |
| order_lines | bigint |  |
| refunded_lines | bigint |  |
| defective_lines | bigint |  |

## `metrics.metric_catalog`

Certified metric catalogue (source of truth for Power BI and the Copilot).

| column | type | description |
|---|---|---|
| metric_name | text |  |
| display_name | text |  |
| owner | text |  |
| unit | text |  |
| direction | text |  |
| is_ratio | boolean |  |
| numerator | text |  |
| denominator | text |  |
| definition | text |  |
| certified | boolean |  |
| catalog_published_at | timestamp with time zone |  |

## `metrics.metrics_daily`

Governed daily metrics. Grain: one row per date. Ratios stored with numerator & denominator.

| column | type | description |
|---|---|---|
| date_day | date | Calendar date (IST). |
| orders | bigint | Count of countable orders. |
| placed_orders | bigint |  |
| cancelled_orders | bigint |  |
| payment_failed_orders | bigint |  |
| gross_revenue | numeric | Governed: qty x selling price on countable orders (after markdowns, before coupons/refunds). |
| coupon_discount | numeric | Order-level coupon discount on countable orders. |
| return_refund_amount | numeric |  |
| net_revenue | numeric | Governed: gross revenue - coupon discounts - processed return refunds. |
| net_cogs | numeric | COGS minus cost recovered on restockable returns. |
| gross_profit | numeric | Governed: net revenue - net COGS. |
| shipping_fee_collected | numeric |  |
| variable_fulfilment_cost | numeric |  |
| contribution_margin | numeric | Governed: gross profit + shipping fees - shipping cost - payment fees - marketplace commission. |
| aov_orders | bigint | AOV denominator: countable non-bulk orders. |
| aov_order_value | numeric | AOV numerator: gross - coupons on countable non-bulk orders. |
| new_customers | bigint | Customers whose first completed order falls in the period. |
| paid_new_customers | bigint | New customers whose first order is attributed to a paid campaign. |
| attributed_net_revenue | numeric |  |
| web_app_net_revenue | numeric |  |
| sessions | bigint | Non-bot web/app sessions. |
| checkout_sessions | bigint | Non-bot sessions that began checkout. |
| purchase_sessions | bigint | Non-bot sessions with a purchase event. |
| bot_sessions | bigint |  |
| payment_attempts | bigint | Prepaid payment attempts (COD excluded). |
| successful_payment_attempts | bigint | Successful prepaid payment attempts. |
| marketing_spend | numeric | Net marketing spend (credit notes netted). |
| acquisition_spend | numeric | Net spend of acquisition-objective campaigns (excludes email/CRM). |
| contribution_margin_after_marketing | numeric | Contribution margin minus net marketing spend (date/channel grain only). |
| aov | numeric | Average order value = aov_order_value / aov_orders. |
| conversion_rate | numeric | purchase_sessions / sessions. |
| checkout_conversion_rate | numeric |  |
| payment_success_rate | numeric | successful_payment_attempts / payment_attempts. |
| refund_rate | numeric | return refunds / gross revenue (order-date basis). |
| cm_pct | numeric | contribution margin / net revenue. |
| cac | numeric | acquisition_spend / paid_new_customers. |
| roas | numeric | attributed net revenue / marketing spend. |
| revenue_per_visitor | numeric |  |
| is_refund_mature | boolean |  |

## `metrics.metrics_daily_by_dimension`

Grain: (date, dimension_name, dimension_value). Components only.

| column | type | description |
|---|---|---|
| date_day | date | Calendar date (IST). |
| dimension_name | text | Dimension of the breakdown row. |
| dimension_value | text | Value of the dimension. |
| orders | numeric | Count of countable orders. |
| gross_revenue | numeric | Governed: qty x selling price on countable orders (after markdowns, before coupons/refunds). |
| net_revenue | numeric | Governed: gross revenue - coupon discounts - processed return refunds. |
| return_refund_amount | numeric |  |
| contribution_margin | numeric | Governed: gross profit + shipping fees - shipping cost - payment fees - marketplace commission. |
| aov_orders | numeric | AOV denominator: countable non-bulk orders. |
| aov_order_value | numeric | AOV numerator: gross - coupons on countable non-bulk orders. |
| sessions | numeric | Non-bot web/app sessions. |
| checkout_sessions | numeric | Non-bot sessions that began checkout. |
| purchase_sessions | numeric | Non-bot sessions with a purchase event. |
| payment_attempts | numeric | Prepaid payment attempts (COD excluded). |
| successful_payment_attempts | numeric | Successful prepaid payment attempts. |

## `metrics.metrics_monthly`

Grain: one row per month. Executive roll-up incl. retention/churn/LTV and MoM/YoY.

| column | type | description |
|---|---|---|
| month | date | First day of the month. |
| orders | numeric | Count of countable orders. |
| gross_revenue | numeric | Governed: qty x selling price on countable orders (after markdowns, before coupons/refunds). |
| coupon_discount | numeric | Order-level coupon discount on countable orders. |
| return_refund_amount | numeric |  |
| net_revenue | numeric | Governed: gross revenue - coupon discounts - processed return refunds. |
| gross_profit | numeric | Governed: net revenue - net COGS. |
| contribution_margin | numeric | Governed: gross profit + shipping fees - shipping cost - payment fees - marketplace commission. |
| marketing_spend | numeric | Net marketing spend (credit notes netted). |
| acquisition_spend | numeric | Net spend of acquisition-objective campaigns (excludes email/CRM). |
| contribution_margin_after_marketing | numeric | Contribution margin minus net marketing spend (date/channel grain only). |
| aov_orders | numeric | AOV denominator: countable non-bulk orders. |
| aov_order_value | numeric | AOV numerator: gross - coupons on countable non-bulk orders. |
| new_customers | numeric | Customers whose first completed order falls in the period. |
| paid_new_customers | numeric | New customers whose first order is attributed to a paid campaign. |
| sessions | numeric | Non-bot web/app sessions. |
| purchase_sessions | numeric | Non-bot sessions with a purchase event. |
| checkout_sessions | numeric | Non-bot sessions that began checkout. |
| payment_attempts | numeric | Prepaid payment attempts (COD excluded). |
| successful_payment_attempts | numeric | Successful prepaid payment attempts. |
| attributed_net_revenue | numeric |  |
| web_app_net_revenue | numeric |  |
| active_customers | bigint |  |
| aov | numeric | Average order value = aov_order_value / aov_orders. |
| conversion_rate | numeric | purchase_sessions / sessions. |
| payment_success_rate | numeric | successful_payment_attempts / payment_attempts. |
| refund_rate | numeric | return refunds / gross revenue (order-date basis). |
| cm_pct | numeric | contribution margin / net revenue. |
| cac | numeric | acquisition_spend / paid_new_customers. |
| blended_cac | numeric |  |
| roas | numeric | attributed net revenue / marketing spend. |
| revenue_per_visitor | numeric |  |
| cohort_customers_90d | bigint |  |
| repeaters_90d | bigint |  |
| repeat_purchase_rate_90d | numeric |  |
| cohort_customers_180d | bigint |  |
| cm_180d | numeric |  |
| ltv_180d_cm | numeric |  |
| active_base | bigint |  |
| churned_customers | bigint |  |
| churn_rate_90d | numeric |  |
| net_revenue_mom | numeric |  |
| net_revenue_yoy | numeric |  |
| cm_yoy | numeric |  |
