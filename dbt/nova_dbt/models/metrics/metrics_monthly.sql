-- grain: ONE ROW PER MONTH. Executive roll-up with MoM / YoY and the cohort-based customer metrics
-- (retention, churn, repeat rate, LTV) that are not meaningful at daily grain.
with d as (
    select date_trunc('month', date_day)::date as month,
           sum(orders) as orders, sum(gross_revenue) as gross_revenue, sum(coupon_discount) as coupon_discount,
           sum(return_refund_amount) as return_refund_amount, sum(net_revenue) as net_revenue,
           sum(gross_profit) as gross_profit, sum(contribution_margin) as contribution_margin,
           sum(marketing_spend) as marketing_spend, sum(acquisition_spend) as acquisition_spend,
           sum(contribution_margin_after_marketing) as contribution_margin_after_marketing,
           sum(aov_orders) as aov_orders, sum(aov_order_value) as aov_order_value,
           sum(new_customers) as new_customers, sum(paid_new_customers) as paid_new_customers,
           sum(sessions) as sessions, sum(purchase_sessions) as purchase_sessions,
           sum(checkout_sessions) as checkout_sessions, sum(payment_attempts) as payment_attempts,
           sum(successful_payment_attempts) as successful_payment_attempts,
           sum(attributed_net_revenue) as attributed_net_revenue, sum(web_app_net_revenue) as web_app_net_revenue
    from {{ ref('metrics_daily') }} group by 1
),
active as (
    select month, count(*) filter (where is_active) as active_customers
    from {{ ref('fct_customer_monthly') }} group by 1
),
rep as (   -- 90-day repeat purchase rate by acquisition month (mature cohorts only)
    select cohort_month as month, count(*) filter (where is_mature_90d) as cohort_customers_90d,
           count(*) filter (where is_mature_90d and repeated_within_90d) as repeaters_90d,
           count(*) filter (where is_mature_180d) as cohort_customers_180d,
           sum(cm_180d) filter (where is_mature_180d) as cm_180d
    from {{ ref('mart_customer_ltv') }} group by 1
),
co as (
    select distinct customer_id, order_date from {{ ref('fct_orders') }}
    where is_countable and customer_id is not null and not is_orphan_customer
),
ms as (select distinct month from d),
base as (   -- customers active in the 90 days before month start
    select ms.month, co.customer_id
    from ms join co on co.order_date >= ms.month - {{ var("churn_inactivity_days") }} and co.order_date < ms.month
    group by 1, 2
),
churn as (
    select b.month, count(*) as active_base,
           count(*) filter (where n.customer_id is null) as churned_customers
    from base b
    left join (select distinct b2.month, b2.customer_id
               from base b2 join co on co.customer_id = b2.customer_id
                and co.order_date >= b2.month and co.order_date < b2.month + {{ var("churn_inactivity_days") }}) n
      on n.month = b.month and n.customer_id = b.customer_id
    where b.month + {{ var("churn_inactivity_days") }} <= '{{ var("data_end_date") }}'::date + 1
    group by 1
)
select d.*, a.active_customers,
       round(d.aov_order_value / nullif(d.aov_orders, 0), 2)                     as aov,
       round(d.purchase_sessions::numeric / nullif(d.sessions, 0), 5)            as conversion_rate,
       round(d.successful_payment_attempts::numeric / nullif(d.payment_attempts, 0), 5) as payment_success_rate,
       round(d.return_refund_amount / nullif(d.gross_revenue, 0), 5)             as refund_rate,
       round(d.contribution_margin / nullif(d.net_revenue, 0), 5)                as cm_pct,
       round(d.acquisition_spend / nullif(d.paid_new_customers, 0), 2)           as cac,
       round(d.acquisition_spend / nullif(d.new_customers, 0), 2)                as blended_cac,
       round(d.attributed_net_revenue / nullif(d.marketing_spend, 0), 4)         as roas,
       round(d.web_app_net_revenue / nullif(d.sessions, 0), 2)                   as revenue_per_visitor,
       r.cohort_customers_90d, r.repeaters_90d,
       round(r.repeaters_90d::numeric / nullif(r.cohort_customers_90d, 0), 4)    as repeat_purchase_rate_90d,
       r.cohort_customers_180d, r.cm_180d, round(r.cm_180d / nullif(r.cohort_customers_180d, 0), 2) as ltv_180d_cm,
       c.active_base, c.churned_customers,
       round(c.churned_customers::numeric / nullif(c.active_base, 0), 4)          as churn_rate_90d,
       round(d.net_revenue / nullif(lag(d.net_revenue) over (order by d.month), 0) - 1, 4)     as net_revenue_mom,
       round(d.net_revenue / nullif(lag(d.net_revenue, 12) over (order by d.month), 0) - 1, 4) as net_revenue_yoy,
       round(d.contribution_margin / nullif(lag(d.contribution_margin, 12) over (order by d.month), 0) - 1, 4) as cm_yoy
from d
left join active a using (month)
left join rep r using (month)
left join churn c using (month)
order by d.month
