/* =====================================================================================
Q03  Decompose MoM net-revenue change into VOLUME (orders) and VALUE (net revenue per order) effects
-------------------------------------------------------------------------------------
BUSINESS QUESTION  "Revenue fell 6% last month" - is it fewer orders or cheaper orders?
WHY IT WORKS       R = N x V.  dR = (N1-N0)*V0  [volume]  +  (V1-V0)*N1  [value].  The two effects sum
                   exactly to dR (no unexplained residual) because the value effect uses N1.
WHY THIS WAY       LAG() gives prior-month N and V on the same row, avoiding a self-join.
PITFALL            Don't decompose with AOV that excludes bulk orders while R includes them - the effects
                   would no longer sum to the total change. Here V = net revenue / completed orders.
AT SCALE           Run on metrics_monthly; add a dimension (channel) to PARTITION BY for mix analysis.
===================================================================================== */
with m as (
    select month, net_revenue as r, orders as n, net_revenue / nullif(orders, 0) as v
    from metrics.metrics_monthly
),
l as (
    select *, lag(r) over (order by month) as r0, lag(n) over (order by month) as n0,
           lag(v) over (order by month) as v0
    from m
)
select month, round(r, 0) as net_revenue, round(r - r0, 0) as change,
       round((n - n0) * v0, 0) as volume_effect,
       round((v - v0) * n, 0)  as value_effect,
       round(((n - n0) * v0) / nullif(r - r0, 0), 3) as share_explained_by_volume
from l where r0 is not null
order by month;
