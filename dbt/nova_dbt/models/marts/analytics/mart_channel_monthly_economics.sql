-- grain: ONE ROW PER (MONTH, CHANNEL). Unit economics: spend, CAC, ROAS, CM after marketing, LTV:CAC.
with months as (select distinct month_start as month from {{ ref('dim_date') }} where is_in_reporting_window),
ch as (select channel from {{ ref('dim_channel') }}),
spend as (
    select date_trunc('month', spend_date)::date as month, channel, sum(spend_inr) as marketing_spend,
           sum(spend_inr) filter (where is_acquisition_spend) as acquisition_spend
    from {{ ref('fct_marketing_spend') }} group by 1, 2
),
ord as (
    select order_month as month, attributed_channel as channel,
           sum(net_revenue) as net_revenue, sum(contribution_margin) as contribution_margin,
           sum(completed_orders) as orders, sum(case when is_first_order then 1 else 0 end) as new_customers,
           sum(net_revenue) filter (where campaign_id is not null) as campaign_attributed_net_revenue
    from {{ ref('fct_orders') }} where is_countable group by 1, 2
),
ltv as (
    select date_trunc('month', first_order_date)::date as month, first_order_channel as channel,
           count(*) filter (where is_mature_90d) as mature_90d_customers, sum(cm_90d) filter (where is_mature_90d) as cm_90d,
           count(*) filter (where is_mature_180d) as mature_180d_customers, sum(cm_180d) filter (where is_mature_180d) as cm_180d
    from {{ ref('mart_customer_ltv') }} group by 1, 2
)
select m.month, ch.channel,
       coalesce(s.marketing_spend, 0) as marketing_spend, coalesce(s.acquisition_spend, 0) as acquisition_spend,
       coalesce(o.orders, 0) as orders, coalesce(o.new_customers, 0) as new_customers,
       coalesce(o.net_revenue, 0) as net_revenue, coalesce(o.contribution_margin, 0) as contribution_margin,
       coalesce(o.contribution_margin, 0) - coalesce(s.marketing_spend, 0) as contribution_margin_after_marketing,
       coalesce(o.campaign_attributed_net_revenue, 0) as campaign_attributed_net_revenue,
       round(s.acquisition_spend / nullif(o.new_customers, 0), 2) as cac,
       round(o.net_revenue / nullif(s.marketing_spend, 0), 3) as roas,
       l.mature_90d_customers, l.cm_90d, round(l.cm_90d / nullif(l.mature_90d_customers, 0), 2) as ltv_90d_cm,
       l.mature_180d_customers, l.cm_180d, round(l.cm_180d / nullif(l.mature_180d_customers, 0), 2) as ltv_180d_cm,
       round((l.cm_180d / nullif(l.mature_180d_customers, 0)) / nullif(s.acquisition_spend / nullif(o.new_customers, 0), 0), 2)
           as ltv180_to_cac
from months m
cross join ch
left join spend s on s.month = m.month and s.channel = ch.channel
left join ord o on o.month = m.month and o.channel = ch.channel
left join ltv l on l.month = m.month and l.channel = ch.channel
where coalesce(s.marketing_spend, 0) <> 0 or coalesce(o.orders, 0) <> 0
