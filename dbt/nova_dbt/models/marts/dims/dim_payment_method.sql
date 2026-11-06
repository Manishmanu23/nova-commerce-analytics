select distinct payment_method, is_prepaid from {{ ref('payment_method_mapping') }}
union all select 'Unknown', null
