-- grain: ONE ROW PER PAYMENT ATTEMPT (after webhook-replay de-dup)
select p.payment_id, p.order_id, p.attempt_no, p.payment_at, p.payment_date,
       to_char(p.payment_date, 'YYYYMMDD')::int as payment_date_key,
       p.payment_method, p.gateway, p.gateway <> 'cod' as is_prepaid_attempt, p.amount_inr, p.payment_status,
       p.is_success, p.failure_reason, p.gateway_fee_inr,
       o.device_type, o.app_version, o.order_channel, o.geo_id, o.is_reportable
from {{ ref('stg_payments') }} p
join {{ ref('fct_orders') }} o using (order_id)
