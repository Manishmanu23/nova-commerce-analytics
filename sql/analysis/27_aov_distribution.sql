/* =====================================================================================
Q27  AOV: mean vs median vs trimmed, by order channel, with/without B2B bulk orders
-------------------------------------------------------------------------------------
BUSINESS QUESTION  Is "AOV went up" real, or did a few bulk orders move the mean?
WHY IT WORKS       percentile_cont for median/p90; governed AOV excludes bulk orders (is_bulk_order).
===================================================================================== */
select order_channel,
       count(*) as orders,
       round(avg(items_gross_revenue_inr - coupon_discount_inr), 0) as mean_incl_bulk,
       round(avg(items_gross_revenue_inr - coupon_discount_inr) filter (where not is_bulk_order), 0) as governed_aov,
       round(percentile_cont(0.5) within group (order by items_gross_revenue_inr - coupon_discount_inr)::numeric, 0) as median,
       round(percentile_cont(0.9) within group (order by items_gross_revenue_inr - coupon_discount_inr)::numeric, 0) as p90,
       count(*) filter (where is_bulk_order) as bulk_orders
from marts.fct_orders where is_countable
group by 1 order by 1;
