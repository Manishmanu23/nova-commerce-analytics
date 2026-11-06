-- grain: one row per ticket
select t.ticket_id, nullif(t.customer_id, '') as customer_id, nullif(t.order_id, '') as order_id,
       {{ to_ist('t.created_ts') }} as created_at, coalesce(m.ticket_category, 'other') as ticket_category,
       t.contact_channel, t.priority, {{ to_ist('t.resolved_ts') }} as resolved_at,
       {{ safe_int('t.csat_score') }}::int as csat_score
from ({{ dedupe(source('raw','customer_support'), 'ticket_id', '_loaded_at desc') }}) t
left join {{ ref('ticket_category_mapping') }} m on m.raw_value = {{ norm('t.category') }}
