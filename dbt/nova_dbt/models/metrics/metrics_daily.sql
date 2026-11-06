-- grain: ONE ROW PER DATE. The governed metric layer.
-- Every ratio is stored WITH its numerator and denominator so it can be re-aggregated correctly
-- to week/month (sum numerators / sum denominators - never average daily ratios).
-- Power BI, the anomaly detector and the Analytics Copilot all read from here => one number everywhere.
with d as (select date_day from {{ ref('dim_date') }} where is_in_reporting_window),
o as (
    select order_date as date_day,
           sum(completed_orders) as orders, sum(gross_revenue) as gross_revenue, sum(coupon_discount) as coupon_discount,
           sum(return_refunds) as return_refund_amount, sum(net_revenue) as net_revenue, sum(net_cogs) as net_cogs,
           sum(gross_profit) as gross_profit, sum(shipping_fee_collected) as shipping_fee_collected,
           sum(variable_fulfilment_cost) as variable_fulfilment_cost, sum(contribution_margin) as contribution_margin,
           sum(aov_orders) as aov_orders, sum(aov_order_value) as aov_order_value,
           sum(case when is_countable and is_first_order then 1 else 0 end) as new_customers,
           sum(case when is_countable and is_first_order and campaign_id is not null
                         and attributed_channel in ('paid_search','paid_social','affiliate','marketplace') then 1 else 0 end) as paid_new_customers,
           sum(net_revenue) filter (where campaign_id is not null) as attributed_net_revenue,
           sum(net_revenue) filter (where order_channel in ('web', 'app')) as web_app_net_revenue,
           count(*) filter (where is_cancelled and is_reportable) as cancelled_orders,
           count(*) filter (where is_payment_failed and is_reportable) as payment_failed_orders,
           count(*) filter (where is_reportable) as placed_orders
    from {{ ref('fct_orders') }} group by 1
),
s as (
    select session_date as date_day, count(*) filter (where not is_bot) as sessions,
           count(*) filter (where not is_bot and has_begin_checkout) as checkout_sessions,
           count(*) filter (where not is_bot and has_purchase) as purchase_sessions,
           count(*) filter (where is_bot) as bot_sessions
    from {{ ref('fct_sessions') }} group by 1
),
p as (
    select payment_date as date_day, count(*) as payment_attempts, count(*) filter (where is_success) as successful_payment_attempts
    from {{ ref('fct_payments') }} where is_prepaid_attempt and is_reportable group by 1
),
m as (
    select spend_date as date_day, sum(spend_inr) as marketing_spend,
           sum(spend_inr) filter (where is_acquisition_spend) as acquisition_spend
    from {{ ref('fct_marketing_spend') }} group by 1
)
select
    d.date_day,
    -- additive components
    coalesce(o.orders, 0) as orders, coalesce(o.placed_orders, 0) as placed_orders,
    coalesce(o.cancelled_orders, 0) as cancelled_orders, coalesce(o.payment_failed_orders, 0) as payment_failed_orders,
    coalesce(o.gross_revenue, 0) as gross_revenue, coalesce(o.coupon_discount, 0) as coupon_discount,
    coalesce(o.return_refund_amount, 0) as return_refund_amount, coalesce(o.net_revenue, 0) as net_revenue,
    coalesce(o.net_cogs, 0) as net_cogs, coalesce(o.gross_profit, 0) as gross_profit,
    coalesce(o.shipping_fee_collected, 0) as shipping_fee_collected,
    coalesce(o.variable_fulfilment_cost, 0) as variable_fulfilment_cost,
    coalesce(o.contribution_margin, 0) as contribution_margin,
    coalesce(o.aov_orders, 0) as aov_orders, coalesce(o.aov_order_value, 0) as aov_order_value,
    coalesce(o.new_customers, 0) as new_customers, coalesce(o.paid_new_customers, 0) as paid_new_customers,
    coalesce(o.attributed_net_revenue, 0) as attributed_net_revenue,
    coalesce(o.web_app_net_revenue, 0) as web_app_net_revenue,
    coalesce(s.sessions, 0) as sessions, coalesce(s.checkout_sessions, 0) as checkout_sessions,
    coalesce(s.purchase_sessions, 0) as purchase_sessions, coalesce(s.bot_sessions, 0) as bot_sessions,
    coalesce(p.payment_attempts, 0) as payment_attempts,
    coalesce(p.successful_payment_attempts, 0) as successful_payment_attempts,
    coalesce(m.marketing_spend, 0) as marketing_spend, coalesce(m.acquisition_spend, 0) as acquisition_spend,
    coalesce(o.contribution_margin, 0) - coalesce(m.marketing_spend, 0) as contribution_margin_after_marketing,
    -- ratios (convenience; recompute from components when aggregating)
    round(o.aov_order_value / nullif(o.aov_orders, 0), 2)                         as aov,
    round(s.purchase_sessions::numeric / nullif(s.sessions, 0), 5)                as conversion_rate,
    round(s.purchase_sessions::numeric / nullif(s.checkout_sessions, 0), 5)       as checkout_conversion_rate,
    round(p.successful_payment_attempts::numeric / nullif(p.payment_attempts, 0), 5) as payment_success_rate,
    round(o.return_refund_amount / nullif(o.gross_revenue, 0), 5)                 as refund_rate,
    round(o.contribution_margin / nullif(o.net_revenue, 0), 5)                    as cm_pct,
    round(m.acquisition_spend / nullif(o.paid_new_customers, 0), 2)               as cac,
    round(o.attributed_net_revenue / nullif(m.marketing_spend, 0), 4)             as roas,
    round(o.web_app_net_revenue / nullif(s.sessions, 0), 2)                       as revenue_per_visitor,
    -- maturity: refunds arrive up to ~3 weeks after order; recent refund rates are incomplete
    d.date_day <= '{{ var("data_end_date") }}'::date - 21                         as is_refund_mature
from d
left join o using (date_day)
left join s using (date_day)
left join p using (date_day)
left join m using (date_day)
