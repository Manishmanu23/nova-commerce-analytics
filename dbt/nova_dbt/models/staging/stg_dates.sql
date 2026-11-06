-- grain: one row per calendar date (festival calendar maintained by the business)
select {{ safe_date('date_day') }} as date_day,
       nullif(trim(festival_name), '') as festival_name,
       coalesce({{ safe_int('is_sale_period') }}, 0) = 1 as is_sale_period,
       fiscal_year, fiscal_quarter
from {{ source('raw','dates') }}
