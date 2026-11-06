-- grain: one row per refund_id. Negative amounts from one source are sign-corrected (flagged).
with typed as (
    select refund_id, order_id, nullif(order_item_id, '') as order_item_id, {{ to_ist('refund_ts') }} as refund_at,
           {{ safe_numeric('refund_amount') }} as refund_amount_raw, refund_reason, lower(refund_status) as refund_status,
           {{ to_ist('_extracted_at') }} as extracted_at, _loaded_at, _batch_id
    from {{ source('raw','refunds') }}
)
select refund_id, order_id, order_item_id, refund_at, refund_at::date as refund_date,
       abs(refund_amount_raw) as refund_amount_inr, refund_amount_raw < 0 as is_sign_corrected,
       refund_reason, refund_status,
       (refund_reason = 'order_cancelled' or order_item_id is null) as is_cancellation_refund,
       extracted_at, _batch_id as batch_id,
       extract(epoch from (extracted_at - refund_at)) / 86400.0 as arrival_lag_days
from ({{ dedupe('typed', 'refund_id', '_loaded_at desc') }}) d
