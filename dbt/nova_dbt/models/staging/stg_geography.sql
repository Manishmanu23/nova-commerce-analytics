-- grain: one row per geo_id
with d as ({{ dedupe(source('raw','geography'), 'geo_id', '_loaded_at desc') }})
select geo_id, trim(city) as city, trim(state) as state, trim(region) as region,
       {{ safe_int('city_tier') }}::int as city_tier
from d
