-- grain: one row per product VERSION (SCD Type 2) + Unknown member for orphan product ids
select product_version_key, product_id, sku, product_name, category, subcategory, brand, list_price, unit_cost,
       round(1 - unit_cost / nullif(list_price, 0), 4) as list_margin_pct, is_cost_imputed,
       version_number, valid_from, valid_to, is_current
from {{ ref('int_products__scd2') }}
union all
select 'unknown', null, null, 'Unknown product', 'Unknown', 'Unknown', 'Unknown', null, null, null, true, 1,
       '1900-01-01'::timestamp, '{{ var("far_future") }}'::timestamp, true
