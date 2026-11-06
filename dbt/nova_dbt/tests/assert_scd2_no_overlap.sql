-- SCD2 integrity: versions of the same customer / product must not overlap in time.
select 'customer' as entity, a.customer_id as id
from {{ ref('int_customers__scd2') }} a
join {{ ref('int_customers__scd2') }} b
  on a.customer_id = b.customer_id and a.customer_version_key <> b.customer_version_key
 and a.valid_from < b.valid_to and b.valid_from < a.valid_to
union all
select 'product', a.product_id
from {{ ref('int_products__scd2') }} a
join {{ ref('int_products__scd2') }} b
  on a.product_id = b.product_id and a.product_version_key <> b.product_version_key
 and a.valid_from < b.valid_to and b.valid_from < a.valid_to
