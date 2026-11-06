-- grain: one row per order_item_id (exact duplicate lines removed)
with typed as (
    select order_item_id, order_id, product_id, {{ safe_int('quantity') }}::int as quantity,
           {{ safe_numeric('unit_list_price') }} as unit_list_price,
           {{ safe_numeric('unit_sale_price') }} as unit_sale_price, _loaded_at
    from {{ source('raw','order_items') }}
)
select order_item_id, order_id, product_id, quantity, unit_list_price, unit_sale_price
from ({{ dedupe('typed', 'order_item_id', '_loaded_at desc') }}) d
