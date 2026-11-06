-- grain: one row per geo_id (+ an explicit Unknown member so fact FKs are never NULL)
select geo_id, city, state, region, city_tier from {{ ref('stg_geography') }}
union all
select '-1', 'Unknown', 'Unknown', 'Unknown', null
