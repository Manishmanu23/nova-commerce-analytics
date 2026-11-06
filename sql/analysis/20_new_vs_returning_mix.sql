/* =====================================================================================
Q20  New vs returning customer revenue & margin mix by month
-------------------------------------------------------------------------------------
BUSINESS QUESTION  Is growth coming from acquisition (expensive) or retention (cheap)?
WHY IT WORKS       customer_type is derived from customer_order_number (1 = new). Share via window SUM.
NOTE               Guests and orphan orders are 'n/a' (no reliable identity) - shown, not hidden.
===================================================================================== */
select order_month, customer_type, sum(completed_orders) as orders, round(sum(net_revenue)) as net_revenue,
       round(sum(contribution_margin) / nullif(sum(net_revenue), 0), 4) as cm_pct,
       round(sum(net_revenue) / sum(sum(net_revenue)) over (partition by order_month), 4) as share_of_net_revenue
from marts.fct_orders where is_countable
group by 1, 2 order by 1, 2;
