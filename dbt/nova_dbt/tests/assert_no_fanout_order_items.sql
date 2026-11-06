-- Grain guard: the line-item fact must have exactly one row per de-duplicated source line.
-- A bad join (e.g. to a non-unique SCD2 window) would silently multiply revenue.
select f.n as fact_rows, s.n as staging_rows
from (select count(*) n from {{ ref('fct_order_items') }}) f
cross join (select count(*) n from {{ ref('stg_order_items') }}) s
where f.n <> s.n
