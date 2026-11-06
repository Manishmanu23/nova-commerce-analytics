/* =====================================================================================
Q06  Time between purchases (LAG) and 90-day repeat rate by acquisition segment
-------------------------------------------------------------------------------------
BUSINESS QUESTION  How long until customers come back, and do discount-acquired customers come back at all?
WHY IT WORKS       LAG(order_at) per customer = previous order; the first order has NULL (excluded).
                   Repeat rate uses mart_customer_ltv.is_mature_90d so young customers aren't counted as
                   "didn't repeat" when they simply haven't had 90 days yet (right-censoring).
WHY THIS WAY       percentile_cont gives medians - inter-purchase time is heavily right-skewed; the mean lies.
AT SCALE           The LAG needs a sort by (customer_id, order_at): an index on those columns or a table
                   clustered/sorted by customer lets the planner avoid a full sort.
===================================================================================== */
with gaps as (
    select customer_id, order_at,
           extract(epoch from order_at - lag(order_at) over (partition by customer_id order by order_at)) / 86400 as days_since_prev
    from marts.fct_orders where is_countable and customer_id is not null
)
select l.acquisition_channel,
       l.is_deep_discount_acquired,
       count(distinct l.customer_id) filter (where l.is_mature_90d)                              as mature_customers,
       round(avg(case when l.repeated_within_90d then 1.0 else 0 end) filter (where l.is_mature_90d), 4) as repeat_rate_90d,
       round(percentile_cont(0.5) within group (order by g.days_since_prev)::numeric, 1)         as median_days_between_orders,
       round(percentile_cont(0.9) within group (order by g.days_since_prev)::numeric, 1)         as p90_days_between_orders
from marts.mart_customer_ltv l
left join gaps g on g.customer_id = l.customer_id and g.days_since_prev is not null
group by 1, 2
order by 1, 2;
