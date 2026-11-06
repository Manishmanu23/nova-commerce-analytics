/* =====================================================================================
Q04  7-day and 28-day rolling net revenue and conversion (correctly re-aggregated)
-------------------------------------------------------------------------------------
BUSINESS QUESTION  What is the underlying trend once weekday noise is removed?
WHY IT WORKS       Window frame ROWS BETWEEN 6 PRECEDING AND CURRENT ROW over a gap-free daily spine.
WHY THIS WAY       * Rolling CONVERSION = rolling SUM(purchases) / rolling SUM(sessions), NOT the average
                     of 7 daily rates (that would weight a 1,000-session day like a 10,000-session day).
                   * ROWS (not RANGE) is safe only because metrics_daily has one row per date; with gaps use
                     RANGE BETWEEN INTERVAL '6 days' PRECEDING AND CURRENT ROW.
PERFORMANCE        Single sort by date, window evaluated in one pass. O(n log n).
AT SCALE           Already on a 730-row table; for 1B-row facts, never compute from the fact at query time.
===================================================================================== */
select date_day, net_revenue,
       round(avg(net_revenue) over (order by date_day rows between 6 preceding and current row), 0)  as net_revenue_7d_avg,
       round(avg(net_revenue) over (order by date_day rows between 27 preceding and current row), 0) as net_revenue_28d_avg,
       conversion_rate,
       round(sum(purchase_sessions) over w7::numeric / nullif(sum(sessions) over w7, 0), 5)          as conversion_rate_7d,
       round(avg(conversion_rate) over w7, 5) as conversion_rate_7d_WRONG_avg_of_ratios
from metrics.metrics_daily
window w7 as (order by date_day rows between 6 preceding and current row)
order by date_day;
