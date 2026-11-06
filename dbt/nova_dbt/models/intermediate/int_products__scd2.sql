-- grain: one row per product version. Historical margin must use the cost valid at order time.
-- Missing unit_cost (ERP sync lag) is imputed with the category median cost ratio and FLAGGED.
with p as (select * from {{ ref('stg_products') }}),
ratios as (
    select category, percentile_cont(0.5) within group (order by unit_cost / nullif(list_price, 0)) as median_cost_ratio
    from p where unit_cost is not null group by 1
),
v as (
    select p.*, r.median_cost_ratio,
           row_number() over (partition by product_id order by updated_at) as version_number,
           lead(updated_at) over (partition by product_id order by updated_at) as next_updated_at
    from p left join ratios r using (category)
)
select
    {{ dbt_utils.generate_surrogate_key(['product_id', 'updated_at']) }} as product_version_key,
    product_id, sku, product_name, category, subcategory, brand, list_price,
    coalesce(unit_cost, round((list_price * median_cost_ratio)::numeric, 2)) as unit_cost,
    is_cost_missing as is_cost_imputed, version_number,
    case when version_number = 1 then '1900-01-01'::timestamp else updated_at end as valid_from,
    coalesce(next_updated_at, '{{ var("far_future") }}'::timestamp)             as valid_to,
    next_updated_at is null                                                     as is_current
from v
