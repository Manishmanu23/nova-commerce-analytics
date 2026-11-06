-- Materialised as a TABLE (not a view): the largest source, joined by several models.
{{ config(materialized='table', indexes=[{'columns': ['session_id'], 'unique': True}, {'columns': ['session_date']}]) }}
-- grain: one row per session. Bot traffic is FLAGGED (not deleted) so it stays auditable.
select {{ safe_int('session_id') }} as session_id, nullif(customer_id, '') as customer_id,
       {{ to_ist('session_start_ts') }} as session_start_at, ({{ to_ist('session_start_ts') }})::date as session_date,
       device_type, os, browser, nullif(app_version, '') as app_version, geo_id,
       coalesce(m.channel, 'unknown') as traffic_channel, nullif(utm_campaign, '') as utm_campaign,
       landing_page, {{ safe_int('duration_sec') }}::int as duration_sec,
       (browser ilike '%headless%' or browser ilike '%bot%') as is_bot
from {{ source('raw','web_sessions') }} s
left join {{ ref('channel_mapping') }} m on m.raw_value = {{ norm('s.traffic_channel') }}
