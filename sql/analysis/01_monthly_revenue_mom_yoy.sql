/* =====================================================================================
Q01  Monthly net revenue & contribution margin with MoM and YoY change
-------------------------------------------------------------------------------------
BUSINESS QUESTION  Is growth still profitable? How fast are revenue and CM growing vs last month / last year?
WHY IT WORKS       Aggregate to month FIRST (one row per month), then LAG() over the ordered months.
                   LAG(x, 12) is "same month last year" only because the month spine has no gaps.
WHY WRITTEN THIS WAY
                   * Uses governed columns from fct_orders (already filtered) -> no re-implementation of filters.
                   * Month spine from dim_date guarantees gaps show up as 0, so LAG(…,12) never silently
                     compares to the wrong month.
                   * NULLIF protects against divide-by-zero in early months.
PERFORMANCE        One scan of fct_orders + tiny sort (24 rows). Cost is dominated by the scan.
AT SCALE           Read from metrics_monthly (pre-aggregated) or an incremental monthly aggregate;
                   partition fct_orders by order_month so the scan is pruned to the needed range.
===================================================================================== */
with months as (
    select distinct month_start as month from marts.dim_date where is_in_reporting_window
),
m as (
    select order_month as month, sum(net_revenue) as net_revenue, sum(contribution_margin) as cm,
           sum(completed_orders) as orders
    from marts.fct_orders
    group by 1
)
select ms.month,
       coalesce(m.net_revenue, 0)                                                  as net_revenue,
       coalesce(m.cm, 0)                                                           as contribution_margin,
       round(m.cm / nullif(m.net_revenue, 0), 4)                                   as cm_pct,
       round(m.net_revenue / nullif(lag(m.net_revenue) over w, 0) - 1, 4)          as net_revenue_mom,
       round(m.net_revenue / nullif(lag(m.net_revenue, 12) over w, 0) - 1, 4)      as net_revenue_yoy,
       round(m.cm / nullif(lag(m.cm, 12) over w, 0) - 1, 4)                        as cm_yoy,
       -- margin-rate change in percentage POINTS (not percent) - a common reporting mistake
       round((m.cm / nullif(m.net_revenue, 0) - lag(m.cm, 12) over w / nullif(lag(m.net_revenue, 12) over w, 0)) * 100, 2)
                                                                                   as cm_pct_change_pp_yoy
from months ms
left join m using (month)
window w as (order by ms.month)
order by ms.month;
