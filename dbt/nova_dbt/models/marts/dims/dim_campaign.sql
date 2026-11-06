-- grain: one row per campaign
select c.campaign_id, c.campaign_name, c.channel, ch.channel_name, c.objective, c.first_order_discount_pct,
       c.start_date, c.end_date, (c.end_date - c.start_date + 1) as duration_days,
       c.first_order_discount_pct >= 0.3 as is_deep_discount
from {{ ref('stg_marketing_campaigns') }} c
left join {{ ref('dim_channel') }} ch using (channel)
