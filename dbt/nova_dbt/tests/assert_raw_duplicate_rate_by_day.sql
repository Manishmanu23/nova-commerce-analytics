{{ config(severity='warn') }}
-- Detects re-sent batches: on any day, raw order rows exceeding distinct orders by > 10%.
-- (Staging removes the duplicates; this test tells us the SOURCE misbehaved and when.)
with r as (
    select left(order_ts, 10) as day, count(*) as raw_rows, count(distinct order_id) as distinct_orders
    from {{ source('raw', 'orders') }} group by 1
)
select day, raw_rows, distinct_orders, round(raw_rows::numeric / distinct_orders - 1, 3) as dup_rate
from r where raw_rows > distinct_orders * 1.10 and distinct_orders > 20
