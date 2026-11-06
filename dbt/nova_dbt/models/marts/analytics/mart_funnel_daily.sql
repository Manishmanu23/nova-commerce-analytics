-- grain: ONE ROW PER (DATE, DEVICE, STATE, TRAFFIC CHANNEL, APP VERSION). Non-bot sessions.
select s.session_date as date_day, s.device_type, coalesce(g.state, 'Unknown') as state, s.traffic_channel,
       coalesce(s.app_version, 'n/a') as app_version,
       count(*) as sessions,
       count(*) filter (where s.has_product_view) as product_view_sessions,
       count(*) filter (where s.has_add_to_cart) as add_to_cart_sessions,
       count(*) filter (where s.has_begin_checkout) as checkout_sessions,
       count(*) filter (where s.has_payment_attempt) as payment_attempt_sessions,
       count(*) filter (where s.has_purchase) as purchase_sessions
from {{ ref('fct_sessions') }} s
left join {{ ref('dim_geography') }} g using (geo_id)
where not s.is_bot
group by 1, 2, 3, 4, 5
