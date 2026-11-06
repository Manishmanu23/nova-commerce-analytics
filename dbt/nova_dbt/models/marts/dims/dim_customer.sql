-- grain: one row per customer VERSION (SCD Type 2) + Unknown/Guest member.
-- PII: raw email is NOT exposed in marts; only a hash (for de-dup / joins).
with v as (select * from {{ ref('int_customers__scd2') }}),
first_orders as (
    select customer_id, min(order_at) as first_order_at
    from {{ ref('int_orders__enriched') }}
    where is_completed and is_reportable and customer_id is not null
    group by 1
)
select
    v.customer_version_key, v.customer_id, v.email_hash, v.signup_at, v.signup_at::date as signup_date,
    coalesce(v.geo_id, '-1') as geo_id, g.city, g.state, g.region, g.city_tier,
    v.acquisition_channel, v.signup_campaign_id, v.is_marketing_opt_in, v.is_internal_test,
    v.signup_at < '{{ var("data_start_date") }}'::date as is_legacy_customer,
    f.first_order_at::date as first_order_date,             -- first order IN THE DATA
    case when v.signup_at >= '{{ var("data_start_date") }}'::date
         then date_trunc('month', f.first_order_at)::date end as acquisition_cohort_month,  -- null for legacy
    f.first_order_at is not null as is_buyer,
    v.version_number, v.valid_from, v.valid_to, v.is_current
from v
left join first_orders f using (customer_id)
left join {{ ref('stg_geography') }} g on g.geo_id = v.geo_id
union all
select 'unknown', null, null, null, null, '-1', 'Unknown', 'Unknown', 'Unknown', null, 'unknown', null, false, false,
       false, null, null, false, 1, '1900-01-01'::timestamp, '{{ var("far_future") }}'::timestamp, true
