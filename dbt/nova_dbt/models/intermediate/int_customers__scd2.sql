-- grain: one row per customer version (Type-2 SCD built from CDC rows).
-- Why SCD2: revenue must be attributed to the customer's city/tier AT THE TIME OF THE ORDER.
-- The first version is valid from the beginning of time so that no order can fall "before" a customer exists.
with v as (
    select *,
           row_number() over (partition by customer_id order by updated_at) as version_number,
           lead(updated_at) over (partition by customer_id order by updated_at) as next_updated_at
    from {{ ref('stg_customers') }}
)
select
    {{ dbt_utils.generate_surrogate_key(['customer_id', 'updated_at']) }} as customer_version_key,
    customer_id, email_hash, signup_at, geo_id, acquisition_channel, signup_campaign_id,
    is_marketing_opt_in, is_internal_test, version_number,
    case when version_number = 1 then '1900-01-01'::timestamp else updated_at end as valid_from,
    coalesce(next_updated_at, '{{ var("far_future") }}'::timestamp)             as valid_to,
    next_updated_at is null                                                     as is_current
from v
