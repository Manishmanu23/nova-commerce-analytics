-- grain: one row per product VERSION (product_id, updated_at)
with typed as (
    select product_id, sku, product_name, {{ norm('category') }} as category_raw, trim(subcategory) as subcategory,
           trim(brand) as brand, {{ safe_numeric('list_price') }} as list_price,
           {{ safe_numeric('unit_cost') }} as unit_cost, {{ to_ist('updated_at') }} as updated_at, _loaded_at
    from {{ source('raw','products') }}
),
deduped as ({{ dedupe('typed', 'product_id, updated_at', '_loaded_at desc') }})
select d.product_id, d.sku, d.product_name, coalesce(m.category, 'Unmapped') as category, d.category_raw,
       d.subcategory, d.brand, d.list_price, d.unit_cost, d.unit_cost is null as is_cost_missing, d.updated_at
from deduped d
left join {{ ref('category_mapping') }} m on m.raw_value = d.category_raw
