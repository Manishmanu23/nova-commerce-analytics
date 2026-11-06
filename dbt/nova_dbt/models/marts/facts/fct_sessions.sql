{{ config(indexes=[{'columns': ['session_date']}]) }}
-- grain: ONE ROW PER WEB/APP SESSION (marketplace traffic is not tracked)
select s.session_id, s.session_date, to_char(s.session_date, 'YYYYMMDD')::int as session_date_key,
       s.session_start_at, s.customer_id, s.device_type, s.os, s.browser, s.app_version, s.geo_id,
       case when c.campaign_id is not null then c.channel else s.traffic_channel end as traffic_channel,
       c.campaign_id, s.landing_page, s.duration_sec, s.is_bot, s.n_events,
       s.has_product_view, s.has_add_to_cart, s.has_begin_checkout, s.has_payment_attempt, s.has_purchase,
       s.n_payment_attempts, o.order_id
from {{ ref('int_sessions__funnel') }} s
left join {{ ref('stg_marketing_campaigns') }} c on c.campaign_id = s.utm_campaign
left join (select session_id, min(order_id) as order_id from {{ ref('stg_orders') }}
           where session_id is not null group by 1) o using (session_id)
