-- Freshness relative to the reporting window: the latest governed day must have orders.
select max(order_date) as latest_order_date
from {{ ref('fct_orders') }} where is_countable
having max(order_date) < '{{ var("data_end_date") }}'::date - 1
