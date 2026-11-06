-- grain: ONE ROW PER REFUND TRANSACTION. Note two date perspectives:
--   refund_date  (cash/finance view)   vs   order_date (cohort/quality view - used by governed refund_rate)
select r.refund_id, r.order_id, r.order_item_id, r.refund_at, r.refund_date, o.order_date,
       r.refund_amount_inr, r.refund_reason, r.refund_status, r.is_cancellation_refund,
       not r.is_cancellation_refund as is_return_refund, r.is_sign_corrected, r.batch_id,
       round(r.arrival_lag_days::numeric, 2) as arrival_lag_days,
       case when o.delivered_at is not null
            then round((extract(epoch from (r.refund_at - o.delivered_at)) / 86400)::numeric, 1) end as days_after_delivery,
       i.product_id, coalesce(i.category, 'n/a') as category, coalesce(i.brand, 'n/a') as brand,
       o.attributed_channel, o.payment_method, o.geo_id, o.is_countable
from {{ ref('stg_refunds') }} r
join {{ ref('fct_orders') }} o using (order_id)
left join {{ ref('int_order_items__priced') }} i using (order_item_id)
