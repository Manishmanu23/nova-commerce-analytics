/* =====================================================================================
Q18  Nova Plus: naive member vs non-member comparison, then a pre-period-matched comparison
-------------------------------------------------------------------------------------
BUSINESS QUESTION  "Members order 2x more - should we push membership harder?"
WHY IT MATTERS     Members SELF-SELECT: loyal customers join. The naive gap mixes selection with effect.
APPROACH           Compare members to non-members who had the SAME number of orders in their first 90 days
                   (a crude stratification on pre-treatment behaviour). If the gap shrinks a lot within strata,
                   most of the naive gap was selection. Proper version: python/nova/analytics/causal.py.
===================================================================================== */
with c as (
    select customer_id, is_member_ever, orders_90d, total_orders - orders_90d as orders_after_90d,
           days_observed
    from marts.mart_customer_ltv where is_mature_180d
)
select 'naive' as comparison, null::int as orders_in_first_90d, is_member_ever,
       count(*) as customers, round(avg(orders_after_90d * 30.0 / (days_observed - 90)), 3) as orders_per_month_after_90d
from c group by is_member_ever
union all
select 'stratified', least(orders_90d, 4), is_member_ever, count(*),
       round(avg(orders_after_90d * 30.0 / (days_observed - 90)), 3)
from c group by least(orders_90d, 4), is_member_ever
order by 1, 2 nulls first, 3;
