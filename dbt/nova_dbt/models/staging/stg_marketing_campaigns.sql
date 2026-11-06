-- grain: one row per campaign
select c.campaign_id, c.campaign_name, coalesce(m.channel, 'unknown') as channel, {{ norm('c.channel') }} as channel_raw,
       c.objective, {{ safe_numeric('c.first_order_discount_pct') }} as first_order_discount_pct,
       {{ safe_date('c.start_date') }} as start_date, {{ safe_date('c.end_date') }} as end_date
from ({{ dedupe(source('raw','marketing_campaigns'), 'campaign_id', '_loaded_at desc') }}) c
left join {{ ref('channel_mapping') }} m on m.raw_value = {{ norm('c.channel') }}
