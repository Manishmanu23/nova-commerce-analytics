/* =====================================================================================
Q26  Contribution-to-change: which states / channels explain the latest MoM net-revenue change?
-------------------------------------------------------------------------------------
BUSINESS QUESTION  Revenue moved X% - which segments moved it?
WHY IT WORKS       delta_segment / delta_total = the segment's share of the change. Shares sum to 100%.
WHY THIS WAY       Ranking by ABSOLUTE contribution (not % change) avoids the tiny-segment trap
                   (+300% on a ₹5k base is irrelevant). This is exactly what the Copilot's breakdown tool does.
===================================================================================== */
with m as (
    select date_trunc('month', date_day)::date as month, dimension_name, dimension_value, sum(net_revenue) as nr
    from metrics.metrics_daily_by_dimension
    where dimension_name in ('state', 'channel', 'device_type', 'customer_type')
      and date_day >= '2025-11-01'
    group by 1, 2, 3
),
p as (
    select dimension_name, dimension_value,
           coalesce(sum(nr) filter (where month = '2025-11-01'), 0) as prev,
           coalesce(sum(nr) filter (where month = '2025-12-01'), 0) as curr
    from m group by 1, 2
)
select dimension_name, dimension_value, round(prev) as nov, round(curr) as dec, round(curr - prev) as delta,
       round((curr - prev) / nullif(sum(curr - prev) over (partition by dimension_name), 0), 3) as share_of_change,
       rank() over (partition by dimension_name order by abs(curr - prev) desc) as rnk
from p
order by dimension_name, rnk;
