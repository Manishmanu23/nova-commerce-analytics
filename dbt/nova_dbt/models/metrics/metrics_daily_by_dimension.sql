{{ config(indexes=[{'columns': ['dimension_name', 'date_day']}]) }}
-- grain: ONE ROW PER (DATE, DIMENSION NAME, DIMENSION VALUE). Long format feeds anomaly drill-down & the Copilot.
-- Components only (numerators/denominators); ratios are derived at query time.
with o as (
    select f.order_date as date_day, f.attributed_channel, f.device_type, coalesce(g.state, 'Unknown') as state,
           f.payment_method, f.customer_type, f.order_channel, coalesce(g.city_tier::text, 'Unknown') as city_tier,
           f.completed_orders, f.gross_revenue, f.net_revenue, f.return_refunds, f.contribution_margin,
           f.aov_orders, f.aov_order_value
    from {{ ref('fct_orders') }} f left join {{ ref('dim_geography') }} g using (geo_id)
    where f.is_countable
),
o_long as (
    select o.date_day, x.dimension_name, x.dimension_value,
           sum(completed_orders) as orders, sum(gross_revenue) as gross_revenue, sum(net_revenue) as net_revenue,
           sum(return_refunds) as return_refund_amount, sum(contribution_margin) as contribution_margin,
           sum(aov_orders) as aov_orders, sum(aov_order_value) as aov_order_value,
           0::bigint as sessions, 0::bigint as checkout_sessions, 0::bigint as purchase_sessions,
           0::bigint as payment_attempts, 0::bigint as successful_payment_attempts
    from o cross join lateral (values ('channel', o.attributed_channel), ('device_type', o.device_type),
        ('state', o.state), ('payment_method', o.payment_method), ('customer_type', o.customer_type),
        ('order_channel', o.order_channel), ('city_tier', o.city_tier)) x(dimension_name, dimension_value)
    group by 1, 2, 3
),
i_long as (
    select i.order_date as date_day, x.dimension_name, x.dimension_value,
           0::bigint, sum(gross_revenue), sum(net_revenue), sum(return_refunds), 0::numeric, 0::bigint, 0::numeric,
           0::bigint, 0::bigint, 0::bigint, 0::bigint, 0::bigint
    from {{ ref('fct_order_items') }} i
    cross join lateral (values ('category', i.category), ('brand', i.brand)) x(dimension_name, dimension_value)
    where i.is_countable
    group by 1, 2, 3
),
s as (
    select f.session_date as date_day, f.device_type, coalesce(g.state, 'Unknown') as state, f.traffic_channel,
           f.browser, coalesce(f.app_version, 'n/a') as app_version, f.has_begin_checkout, f.has_purchase
    from {{ ref('fct_sessions') }} f left join {{ ref('dim_geography') }} g using (geo_id)
    where not f.is_bot
),
s_long as (
    select s.date_day, x.dimension_name, x.dimension_value,
           0::bigint, 0::numeric, 0::numeric, 0::numeric, 0::numeric, 0::bigint, 0::numeric,
           count(*), count(*) filter (where has_begin_checkout), count(*) filter (where has_purchase), 0::bigint, 0::bigint
    from s cross join lateral (values ('device_type', s.device_type), ('state', s.state),
        ('traffic_channel', s.traffic_channel), ('browser', s.browser), ('app_version', s.app_version))
        x(dimension_name, dimension_value)
    group by 1, 2, 3
),
p as (
    select p.payment_date as date_day, p.payment_method, p.device_type, coalesce(g.state, 'Unknown') as state,
           coalesce(p.app_version, 'n/a') as app_version, p.is_success
    from {{ ref('fct_payments') }} p left join {{ ref('dim_geography') }} g using (geo_id)
    where p.is_prepaid_attempt and p.is_reportable
),
p_long as (
    select p.date_day, x.dimension_name, x.dimension_value,
           0::bigint, 0::numeric, 0::numeric, 0::numeric, 0::numeric, 0::bigint, 0::numeric,
           0::bigint, 0::bigint, 0::bigint, count(*), count(*) filter (where is_success)
    from p cross join lateral (values ('payment_method', p.payment_method), ('device_type', p.device_type),
        ('state', p.state), ('app_version', p.app_version)) x(dimension_name, dimension_value)
    group by 1, 2, 3
),
u as (select * from o_long union all select * from i_long union all select * from s_long union all select * from p_long)
select date_day, dimension_name, coalesce(dimension_value, 'Unknown') as dimension_value,
       sum(orders) as orders, sum(gross_revenue) as gross_revenue, sum(net_revenue) as net_revenue,
       sum(return_refund_amount) as return_refund_amount, sum(contribution_margin) as contribution_margin,
       sum(aov_orders) as aov_orders, sum(aov_order_value) as aov_order_value, sum(sessions) as sessions,
       sum(checkout_sessions) as checkout_sessions, sum(purchase_sessions) as purchase_sessions,
       sum(payment_attempts) as payment_attempts, sum(successful_payment_attempts) as successful_payment_attempts
from u
where date_day between '{{ var("data_start_date") }}' and '{{ var("data_end_date") }}'
group by 1, 2, 3
