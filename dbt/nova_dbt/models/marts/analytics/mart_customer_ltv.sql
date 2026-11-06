-- grain: ONE ROW PER BUYING CUSTOMER (current version). Customer economics & LTV windows.
-- Maturity flags matter: a customer acquired 30 days ago cannot have a 180-day LTV yet.
-- Averaging immature customers into LTV is the #1 way LTV gets understated (or CAC:LTV overstated).
-- Legacy customers (signed up before the data platform) are EXCLUDED: their true first order is unknown.
with c as (select * from {{ ref('dim_customer') }}
           where is_current and is_buyer and not is_internal_test and not is_legacy_customer),
o as (
    select customer_id, order_at, order_date, net_revenue, contribution_margin, coupon_discount, return_refunds,
           gross_revenue, is_member_order, campaign_id, attributed_channel, customer_order_number
    from {{ ref('fct_orders') }} where is_countable and customer_id is not null and not is_orphan_customer
),
f as (
    select customer_id, order_at as first_order_at, order_date as first_order_date, campaign_id as first_order_campaign_id,
           attributed_channel as first_order_channel, coupon_discount as first_order_coupon, gross_revenue as first_order_gross
    from o where customer_order_number = 1
),
agg as (
    select o.customer_id,
           count(*) as total_orders, sum(net_revenue) as total_net_revenue, sum(contribution_margin) as total_cm,
           max(o.order_date) as last_order_date, bool_or(is_member_order) as is_member_ever,
           count(*) filter (where o.order_at < f.first_order_at + interval '90 days')  as orders_90d,
           sum(net_revenue) filter (where o.order_at < f.first_order_at + interval '90 days')  as net_revenue_90d,
           sum(contribution_margin) filter (where o.order_at < f.first_order_at + interval '90 days')  as cm_90d,
           count(*) filter (where o.order_at < f.first_order_at + interval '180 days') as orders_180d,
           sum(net_revenue) filter (where o.order_at < f.first_order_at + interval '180 days') as net_revenue_180d,
           sum(contribution_margin) filter (where o.order_at < f.first_order_at + interval '180 days') as cm_180d,
           count(*) filter (where o.order_at < f.first_order_at + interval '365 days') as orders_365d,
           sum(net_revenue) filter (where o.order_at < f.first_order_at + interval '365 days') as net_revenue_365d,
           sum(contribution_margin) filter (where o.order_at < f.first_order_at + interval '365 days') as cm_365d
    from o join f using (customer_id) group by 1
)
select
    c.customer_id, c.acquisition_channel, c.signup_campaign_id, dc.first_order_discount_pct as signup_campaign_discount,
    coalesce(dc.is_deep_discount, false) as is_deep_discount_acquired,
    date_trunc('month', f.first_order_date)::date as cohort_month, c.state, c.city_tier,
    f.first_order_date, f.first_order_channel, f.first_order_campaign_id, f.first_order_coupon, f.first_order_gross,
    a.total_orders, a.total_net_revenue, a.total_cm, a.last_order_date, a.is_member_ever,
    a.orders_90d, a.net_revenue_90d, a.cm_90d, a.orders_180d, a.net_revenue_180d, a.cm_180d,
    a.orders_365d, a.net_revenue_365d, a.cm_365d,
    ('{{ var("data_end_date") }}'::date - f.first_order_date)        as days_observed,
    ('{{ var("data_end_date") }}'::date - f.first_order_date) >= 90  as is_mature_90d,
    ('{{ var("data_end_date") }}'::date - f.first_order_date) >= 180 as is_mature_180d,
    ('{{ var("data_end_date") }}'::date - f.first_order_date) >= 365 as is_mature_365d,
    a.orders_90d >= 2                                                as repeated_within_90d,
    ('{{ var("data_end_date") }}'::date - a.last_order_date)         as days_since_last_order,
    ('{{ var("data_end_date") }}'::date - a.last_order_date) > {{ var("churn_inactivity_days") }} as is_churned_90d
from c
join f using (customer_id)
join agg a using (customer_id)
left join {{ ref('dim_campaign') }} dc on dc.campaign_id = c.signup_campaign_id
