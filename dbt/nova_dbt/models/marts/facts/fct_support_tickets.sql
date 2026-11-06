-- grain: ONE ROW PER SUPPORT TICKET
select t.ticket_id, t.customer_id, t.order_id, t.created_at, t.created_at::date as created_date,
       t.ticket_category, t.contact_channel, t.priority, t.resolved_at, t.csat_score,
       t.resolved_at < t.created_at as is_invalid_resolution,
       case when t.resolved_at >= t.created_at
            then round((extract(epoch from (t.resolved_at - t.created_at)) / 3600)::numeric, 1) end as resolution_hours,
       o.device_type, o.payment_method, o.geo_id
from {{ ref('stg_customer_support') }} t
left join {{ ref('fct_orders') }} o using (order_id)
