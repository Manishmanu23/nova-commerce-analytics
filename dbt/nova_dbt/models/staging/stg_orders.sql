-- grain: one row per order_id. The OMS re-sends records on retry; the latest extract wins.
with typed as (
    select
        order_id,
        nullif(customer_id, '')                              as customer_id,
        {{ safe_int('session_id') }}                         as session_id,
        {{ to_ist('order_ts') }}                             as order_at,
        order_channel, nullif(device_type, '')               as device_type, nullif(os, '') as os,
        nullif(geo_id, '')                                   as geo_id,
        {{ norm('payment_method') }}                         as payment_method_raw,
        nullif(coupon_code, '')                              as coupon_code,
        {{ safe_numeric('subtotal_inr') }}                   as subtotal_inr,
        coalesce({{ safe_numeric('coupon_discount_inr') }}, 0)        as coupon_discount_inr,
        coalesce({{ safe_numeric('shipping_fee_inr') }}, 0)           as shipping_fee_inr,
        {{ safe_numeric('order_total_inr') }}                as order_total_inr,
        coalesce({{ safe_numeric('shipping_cost_inr') }}, 0)          as shipping_cost_inr,
        coalesce({{ safe_numeric('marketplace_commission_inr') }}, 0) as marketplace_commission_inr,
        {{ norm('order_status') }}                           as order_status,
        {{ to_ist('shipped_ts') }}                           as shipped_at,
        {{ to_ist('delivered_ts') }}                         as delivered_at,
        {{ to_ist('cancelled_ts') }}                         as cancelled_at,
        source_system,
        {{ to_ist('_extracted_at') }}                        as extracted_at,
        _loaded_at, _batch_id
    from {{ source('raw','orders') }}
),
ranked as (
    select *, count(*) over (partition by order_id) as source_row_count,
           row_number() over (partition by order_id order by extracted_at desc nulls last, _loaded_at desc) as _rn
    from typed
)
select r.order_id, r.customer_id, r.session_id, r.order_at, r.order_at::date as order_date, r.order_channel,
       r.device_type, r.os, r.geo_id, coalesce(pm.payment_method, 'Unknown') as payment_method,
       coalesce(pm.is_prepaid, true) as is_prepaid, r.payment_method_raw, r.coupon_code, r.subtotal_inr,
       r.coupon_discount_inr, r.shipping_fee_inr, r.order_total_inr, r.shipping_cost_inr,
       r.marketplace_commission_inr, r.order_status, r.shipped_at, r.delivered_at, r.cancelled_at,
       r.source_system, r.extracted_at, r.source_row_count, r._loaded_at
from ranked r
left join {{ ref('payment_method_mapping') }} pm on pm.raw_value = r.payment_method_raw
where r._rn = 1
