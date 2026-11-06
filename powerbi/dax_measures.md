# DAX Measure Library

Principles:

1. Measures only **sum governed components**. Business filters (completed, reportable) are already encoded in the columns (ADR-004).
2. Every ratio is `DIVIDE(SUM(numerator), SUM(denominator))`, which re-aggregates correctly at any level.
3. Time intelligence runs on the marked `dim_date`.

## 01 Revenue

```DAX
Gross Revenue      = SUM ( fct_orders[gross_revenue] )
Coupon Discounts   = SUM ( fct_orders[coupon_discount] )
Return Refunds     = SUM ( fct_orders[return_refunds] )
Net Revenue        = SUM ( fct_orders[net_revenue] )
Orders             = SUM ( fct_orders[completed_orders] )
AOV                = DIVIDE ( SUM ( fct_orders[aov_order_value] ), SUM ( fct_orders[aov_orders] ) )

Net Revenue PM     = CALCULATE ( [Net Revenue], DATEADD ( dim_date[date_day], -1, MONTH ) )
Net Revenue MoM %  = DIVIDE ( [Net Revenue] - [Net Revenue PM], [Net Revenue PM] )
Net Revenue PY     = CALCULATE ( [Net Revenue], SAMEPERIODLASTYEAR ( dim_date[date_day] ) )
Net Revenue YoY %  = DIVIDE ( [Net Revenue] - [Net Revenue PY], [Net Revenue PY] )
Net Revenue FYTD   = TOTALYTD ( [Net Revenue], dim_date[date_day], "03-31" )   -- Indian FY ends 31 Mar
Net Revenue 7D Avg =
    AVERAGEX ( DATESINPERIOD ( dim_date[date_day], MAX ( dim_date[date_day] ), -7, DAY ), [Net Revenue] )

-- Indian number formatting helper for cards
Fmt ₹ Net Revenue =
VAR v = [Net Revenue]
RETURN SWITCH ( TRUE (),
    ABS ( v ) >= 1e7, FORMAT ( v / 1e7, "₹0.00" ) & " Cr",
    ABS ( v ) >= 1e5, FORMAT ( v / 1e5, "₹0.0" ) & " L",
    FORMAT ( v, "₹#,##0" ) )
```

## 02 Margin

```DAX
Net COGS                 = SUM ( fct_orders[net_cogs] )
Gross Profit             = SUM ( fct_orders[gross_profit] )
Contribution Margin      = SUM ( fct_orders[contribution_margin] )
CM %                     = DIVIDE ( [Contribution Margin], [Net Revenue] )
Marketing Spend          = SUM ( fct_marketing_spend[spend_inr] )
CM after Marketing       = [Contribution Margin] - [Marketing Spend]      -- valid at date/channel/campaign grain only
CM after Marketing %     = DIVIDE ( [CM after Marketing], [Net Revenue] )
CM % PY                  = CALCULATE ( [CM %], SAMEPERIODLASTYEAR ( dim_date[date_day] ) )
CM % Δ pp YoY            = ( [CM %] - [CM % PY] ) * 100          -- percentage POINTS, not percent
Discount Rate            = DIVIDE ( [Coupon Discounts], [Gross Revenue] )
Refund Rate              = DIVIDE ( [Return Refunds], [Gross Revenue] )
Refund Rate Provisional? =
    IF ( MAX ( dim_date[date_day] ) > DATE ( 2025, 12, 31 ) - 21, "Provisional: refunds still arriving", BLANK () )

-- waterfall (use a disconnected table 'Waterfall Steps'[Step], [Order])
Waterfall Value =
SWITCH ( SELECTEDVALUE ( 'Waterfall Steps'[Step] ),
    "Gross revenue",         [Gross Revenue],
    "Coupons",              -[Coupon Discounts],
    "Refunds",              -[Return Refunds],
    "COGS",                 -[Net COGS],
    "Shipping fees",         SUM ( fct_orders[shipping_fee_collected] ),
    "Fulfilment & fees",    -SUM ( fct_orders[variable_fulfilment_cost] ),
    "Marketing",            -[Marketing Spend] )
```

## 03 Customers

```DAX
New Customers       = CALCULATE ( [Orders], fct_orders[is_first_order] = TRUE () )
Active Customers    = CALCULATE ( DISTINCTCOUNT ( fct_orders[customer_id] ), fct_orders[is_countable] = TRUE () )
Returning Rev Share = DIVIDE ( CALCULATE ( [Net Revenue], fct_orders[customer_type] = "returning" ), [Net Revenue] )

-- cohort retention from the additive mart (never average the % column)
Retention %         = DIVIDE ( SUM ( mart_cohort_retention[active_customers] ), SUM ( mart_cohort_retention[cohort_size] ) )
Cum CM per Customer = DIVIDE ( SUM ( mart_cohort_retention[cumulative_cm] ), SUM ( mart_cohort_retention[cohort_size] ) )

LTV 180d (CM)       = CALCULATE ( AVERAGE ( mart_customer_ltv[cm_180d] ), mart_customer_ltv[is_mature_180d] = TRUE () )
Repeat Rate 90d     =
    CALCULATE ( AVERAGEX ( mart_customer_ltv, INT ( mart_customer_ltv[repeated_within_90d] ) ),
                mart_customer_ltv[is_mature_90d] = TRUE () )
Churn Rate 90d      = DIVIDE ( SUM ( metrics_monthly[churned_customers] ), SUM ( metrics_monthly[active_base] ) )
Member Order Share  = DIVIDE ( CALCULATE ( [Orders], fct_orders[is_member_order] = TRUE () ), [Orders] )
```

## 04 Funnel

```DAX
Sessions               = SUM ( mart_funnel_daily[sessions] )
Checkout Sessions      = SUM ( mart_funnel_daily[checkout_sessions] )
Purchase Sessions      = SUM ( mart_funnel_daily[purchase_sessions] )
Conversion Rate        = DIVIDE ( [Purchase Sessions], [Sessions] )
Checkout Conversion    = DIVIDE ( [Purchase Sessions], [Checkout Sessions] )
View→Cart %            = DIVIDE ( SUM ( mart_funnel_daily[add_to_cart_sessions] ), SUM ( mart_funnel_daily[product_view_sessions] ) )
Payment Success Rate   =
    DIVIDE ( CALCULATE ( COUNTROWS ( fct_payments ), fct_payments[is_success] = TRUE (), fct_payments[is_prepaid_attempt] = TRUE () ),
             CALCULATE ( COUNTROWS ( fct_payments ), fct_payments[is_prepaid_attempt] = TRUE () ) )
Revenue per Visitor    = DIVIDE ( CALCULATE ( [Net Revenue], fct_orders[order_channel] IN { "web", "app" } ), [Sessions] )

-- funnel visual: step as a dimension via a disconnected 'Funnel Steps' table
Funnel Sessions =
SWITCH ( SELECTEDVALUE ( 'Funnel Steps'[Step] ),
    "1 Session",         [Sessions],
    "2 Product view",    SUM ( mart_funnel_daily[product_view_sessions] ),
    "3 Add to cart",     SUM ( mart_funnel_daily[add_to_cart_sessions] ),
    "4 Checkout",        [Checkout Sessions],
    "5 Payment attempt", SUM ( mart_funnel_daily[payment_attempt_sessions] ),
    "6 Purchase",        [Purchase Sessions] )
```

## 05 Marketing

```DAX
Acquisition Spend = CALCULATE ( [Marketing Spend], fct_marketing_spend[is_acquisition_spend] = TRUE () )
Paid New Customers =
    CALCULATE ( [New Customers], NOT ISBLANK ( fct_orders[campaign_id] ),
                fct_orders[attributed_channel] IN { "paid_search", "paid_social", "affiliate", "marketplace" } )
CAC               = DIVIDE ( [Acquisition Spend], [Paid New Customers] )
Blended CAC       = DIVIDE ( [Acquisition Spend], [New Customers] )
ROAS              = DIVIDE ( CALCULATE ( [Net Revenue], NOT ISBLANK ( fct_orders[campaign_id] ) ), [Marketing Spend] )
LTV:CAC           = DIVIDE ( [LTV 180d (CM)], [CAC] )
```

## 06 Quality & anomalies

```DAX
DQ Score           = CALCULATE ( MAX ( dq_scorecard[score] ), dq_scorecard[dimension] = "OVERALL" )
DQ Verdict         = SWITCH ( TRUE (), [DQ Score] >= 90, "Fit", [DQ Score] >= 75, "Fit with caveats", "Not fit" )
Open DQ Warnings   = CALCULATE ( COUNTROWS ( dq_checks ), dq_checks[status] <> "pass" )
Failing dbt Tests  = CALCULATE ( COUNTROWS ( dbt_test_results ), dbt_test_results[status] IN { "fail", "error" },
                                 dbt_test_results[run_at] = MAX ( dbt_test_results[run_at] ) )
Active Incidents   = CALCULATE ( COUNTROWS ( anomaly_alerts ), anomaly_alerts[classification] = "business_signal" )
Segment Incidents  = COUNTROWS ( anomaly_segment_alerts )
```

## 07 Decision simulator (what-if parameters)

Create the What-if parameters: `Retention Δpp` (−3…+3, step 0.5), `Conversion Δ%` (−10…+10), `AOV Δ%` (−10…+10), `CAC Δ%` (−30…+30), `Refund Δpp` (−3…+3), `Discount Δpp` (−5…+5).
The baseline values come from `scenario_baseline` (label **Observed**). This closed form matches `nova.simulator.engine`:

```DAX
Base (param)  = LOOKUPVALUE ( scenario_baseline[value], scenario_baseline[parameter], "base_customers" )
-- helper: get any baseline parameter
P ( name ) pattern: CALCULATE ( MAX ( scenario_baseline[value] ), scenario_baseline[parameter] = "<name>" )

Sim Churn     = MAX ( 0.001, [P churn_m] - [Retention Δpp Value] / 100 )
Sim Conv      = 1 + [Conversion Δ% Value] / 100
Sim New / Mo  = [P acq_spend] / ( [P cac] * ( 1 + [CAC Δ% Value] / 100 ) ) + [P organic_new] * [Sim Conv]
Sim Surv      = 1 - [Sim Churn]
-- total customer-months over 12 months of  B_t = B0*s^t + N*(1-s^t)/(1-s)
Sim Cust-Months =
VAR s = [Sim Surv]  VAR B0 = [Base (param)]  VAR N = [Sim New / Mo]
RETURN SUMX ( GENERATESERIES ( 0, 11 ), B0 * POWER ( s, [Value] ) + N * ( 1 - POWER ( s, [Value] ) ) / ( 1 - s ) )
Sim Orders    = [Sim Cust-Months] * [P orders_per_customer] * [Sim Conv]
Sim Gross     = [Sim Orders] * [P aov_gross] * ( 1 + [AOV Δ% Value] / 100 )
Sim Net Rev   = [Sim Gross] * ( 1 - ( [P discount_rate] + [Discount Δpp Value] / 100 ) - ( [P refund_rate] + [Refund Δpp Value] / 100 ) )
Sim CM        = [Sim Net Rev] - [Sim Gross] * [P cogs_pct] - [Sim Orders] * [P variable_cost_per_order]
Sim CM after Mkt = [Sim CM] - 12 * [P marketing_spend]
Sim Label     = "ESTIMATE: based on assumptions set above, not an actual or a forecast"
```

Every simulator visual carries the `Sim Label` subtitle. Observed baselines appear in a separate card with the label "Observed (H2 2025)".
