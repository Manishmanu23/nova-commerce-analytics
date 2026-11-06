-- grain: one row per customer VERSION (customer_id, updated_at). Exact duplicate CDC rows removed.
with typed as (
    select
        customer_id,
        lower(trim(email))                                  as email,
        {{ to_ist('signup_ts') }}                            as signup_at,
        nullif(geo_id, '')                                   as geo_id,
        {{ norm('acquisition_channel') }}                    as acquisition_channel_raw,
        nullif(signup_campaign_id, '')                       as signup_campaign_id,
        coalesce({{ safe_int('marketing_opt_in') }}, 0) = 1  as is_marketing_opt_in,
        {{ to_ist('updated_at') }}                           as updated_at,
        _loaded_at
    from {{ source('raw','customers') }}
),
deduped as ({{ dedupe('typed', 'customer_id, updated_at', '_loaded_at desc') }})
select
    d.customer_id, d.email, md5(d.email) as email_hash, d.signup_at, d.geo_id,
    coalesce(m.channel, 'unknown')                                   as acquisition_channel,
    d.acquisition_channel_raw, d.signup_campaign_id, d.is_marketing_opt_in, d.updated_at,
    d.email like '%@{{ var("internal_email_domain") }}'               as is_internal_test,
    d._loaded_at
from deduped d
left join {{ ref('channel_mapping') }} m on m.raw_value = d.acquisition_channel_raw
