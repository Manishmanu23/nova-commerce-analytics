-- Materialised as a TABLE (not a view): the largest source, joined by several models.
{{ config(materialized='table', indexes=[{'columns': ['session_id']}]) }}
-- grain: one row per event
select {{ safe_int('event_id') }} as event_id, {{ safe_int('session_id') }} as session_id,
       {{ to_ist('event_ts') }} as event_at, lower(event_name) as event_name, nullif(product_id, '') as product_id
from {{ source('raw','funnel_events') }}
