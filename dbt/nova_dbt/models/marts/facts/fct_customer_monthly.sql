-- grain: ONE ROW PER (CUSTOMER, MONTH) from the customer's first-order month to the end of data.
-- Periodic snapshot: months with no orders are present (is_active = false) - required for retention/churn.
with orders as (
    select customer_id, order_month, bool_or(is_legacy_customer) as is_legacy_customer, count(*) as orders,
           sum(net_revenue) as net_revenue, sum(contribution_margin) as contribution_margin
    from {{ ref('fct_orders') }}
    where is_countable and customer_id is not null and not is_orphan_customer
    group by 1, 2
),
firsts as (select customer_id, min(order_month) as cohort_month, bool_or(is_legacy_customer) as is_legacy_customer
           from orders group by 1),
spine as (
    select f.customer_id, f.cohort_month, f.is_legacy_customer, m::date as month
    from firsts f
    cross join lateral generate_series(f.cohort_month, date_trunc('month', '{{ var("data_end_date") }}'::date), interval '1 month') m
)
-- legacy customers are included (for active-customer counts) but flagged: their "cohort_month" is only
-- the first month we can SEE, so they are excluded from cohort retention / LTV.
select s.customer_id, s.cohort_month, s.is_legacy_customer, s.month,
       ((extract(year from s.month) - extract(year from s.cohort_month)) * 12
         + extract(month from s.month) - extract(month from s.cohort_month))::int as months_since_first,
       coalesce(o.orders, 0) as orders, coalesce(o.net_revenue, 0) as net_revenue,
       coalesce(o.contribution_margin, 0) as contribution_margin, o.orders is not null as is_active,
       sum(coalesce(o.net_revenue, 0)) over (partition by s.customer_id order by s.month) as cumulative_net_revenue,
       sum(coalesce(o.contribution_margin, 0)) over (partition by s.customer_id order by s.month) as cumulative_cm
from spine s
left join orders o on o.customer_id = s.customer_id and o.order_month = s.month
