/* =====================================================================================
Q15  SQL anomaly screen: robust z-score vs same-weekday baseline (median + MAD of prior 8 weeks)
-------------------------------------------------------------------------------------
BUSINESS QUESTION  Which days had abnormal net revenue given the usual weekday pattern?
WHY IT WORKS       Expected = median of the same weekday over the previous 8 weeks; spread = MAD * 1.4826
                   (MAD scaled to be comparable to a standard deviation for normal data).
                   robust_z = (actual - expected) / (1.4826 * MAD).
WHY MEDIAN/MAD     Mean/stddev are pulled by the very outliers we want to find (a Diwali spike inflates the
                   stddev and hides the next anomaly). Median/MAD have a 50% breakdown point.
WHY SAME WEEKDAY   Weekend traffic differs; comparing Saturday to Friday creates false alerts.
PERFORMANCE        LATERAL subquery runs per day (730 x 8 rows) - fine. On a big daily table, compute the
                   baseline with window functions or in Python (python/nova/anomaly) instead.
LIMITS             Screens for "unusual", not "why". Festive days are expected-unusual -> labelled, not alerted.
===================================================================================== */
with d as (
    select m.date_day, m.net_revenue, dd.is_sale_period, dd.festival_name
    from metrics.metrics_daily m join marts.dim_date dd using (date_day)
),
hist as (   -- the same weekday in each of the previous 8 weeks
    select d.date_day, h.net_revenue as hist_value
    from d join d h on (d.date_day - h.date_day) between 7 and 56 and (d.date_day - h.date_day) % 7 = 0
),
med as (
    select date_day, percentile_cont(0.5) within group (order by hist_value) as expected, count(*) as n_hist
    from hist group by 1
),
mad as (
    select h.date_day, percentile_cont(0.5) within group (order by abs(h.hist_value - m.expected)) as mad
    from hist h join med m using (date_day) group by 1
),
scored as (
    select d.*, m.expected, a.mad, (d.net_revenue - m.expected) / nullif(1.4826 * a.mad, 0) as robust_z
    from d join med m using (date_day) join mad a using (date_day)
    where m.n_hist = 8
)
select date_day, round(net_revenue) as actual, round(expected::numeric) as expected,
       round((net_revenue / nullif(expected, 0) - 1)::numeric, 3) as deviation,
       round(robust_z::numeric, 2) as robust_z,
       case when is_sale_period then 'expected (' || festival_name || ')' else 'unexpected' end as context
from scored
where abs(robust_z) > 3.5
order by abs(robust_z) desc
limit 25;
