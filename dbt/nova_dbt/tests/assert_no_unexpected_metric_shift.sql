{{ config(severity='warn') }}
-- "Unexpected metric shift" guard on governed net revenue: flags non-sale days deviating > 100%
-- from the trailing 28-day median. A warning, not a verdict - routes to the anomaly workflow.
with d as (
    select m.date_day, m.net_revenue, dd.is_sale_period,
           (percentile_cont(0.5) within group (order by m2.net_revenue))::numeric as trailing_median
    from {{ ref('metrics_daily') }} m
    join {{ ref('dim_date') }} dd on dd.date_day = m.date_day
    join {{ ref('metrics_daily') }} m2 on m2.date_day between m.date_day - 28 and m.date_day - 1
    where m.date_day >= '{{ var("data_start_date") }}'::date + 60
    group by 1, 2, 3
)
select date_day, net_revenue, trailing_median, round(net_revenue / nullif(trailing_median, 0) - 1, 3) as deviation
from d where not is_sale_period and abs(net_revenue / nullif(trailing_median, 0) - 1) > 1.0
