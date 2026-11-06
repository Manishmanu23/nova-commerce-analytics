-- grain: ONE ROW PER (EXPERIMENT, CUSTOMER) - factless exposure fact with outcome measures.
-- Outcomes only count orders AFTER assignment and BEFORE experiment end (no pre-exposure leakage).
-- pre_period_* (28 days before assignment) supports CUPED variance reduction and balance checks.
with a as (
    select a.*, e.start_date, e.end_date
    from {{ ref('stg_experiment_assignments') }} a
    join {{ ref('stg_experiments') }} e using (experiment_id)
),
o as (select order_id, customer_id, order_at, net_revenue, contribution_margin, shipping_fee_collected, is_countable
      from {{ ref('fct_orders') }} where is_countable)
select
    a.experiment_id, a.customer_id, a.variant, a.assigned_at, a.platform,
    count(o.order_id) filter (where o.order_at >= a.assigned_at and o.order_at < a.end_date + 1)          as orders_in_window,
    (count(o.order_id) filter (where o.order_at >= a.assigned_at and o.order_at < a.end_date + 1) > 0)::int as converted,
    coalesce(sum(o.net_revenue) filter (where o.order_at >= a.assigned_at and o.order_at < a.end_date + 1), 0) as net_revenue,
    coalesce(sum(o.contribution_margin) filter (where o.order_at >= a.assigned_at and o.order_at < a.end_date + 1), 0) as contribution_margin,
    coalesce(sum(o.shipping_fee_collected) filter (where o.order_at >= a.assigned_at and o.order_at < a.end_date + 1), 0) as shipping_fee_paid,
    count(o.order_id) filter (where o.order_at >= a.assigned_at - interval '28 days' and o.order_at < a.assigned_at) as pre_period_orders,
    coalesce(sum(o.net_revenue) filter (where o.order_at >= a.assigned_at - interval '28 days' and o.order_at < a.assigned_at), 0) as pre_period_net_revenue
from a
left join o on o.customer_id = a.customer_id
group by 1, 2, 3, 4, 5
