-- grain: one row per real payment attempt.
-- Two de-dup rules: (1) payment_id, (2) gateway_txn_ref (webhook replays create a new payment_id
-- for the SAME gateway transaction - counting both would double-count collections).
with typed as (
    select payment_id, order_id, {{ safe_int('attempt_no') }}::int as attempt_no,
           {{ to_ist('payment_ts') }} as payment_at, {{ norm('payment_method') }} as payment_method_raw,
           gateway, {{ safe_numeric('amount') }} as amount_raw, lower(status) as payment_status,
           nullif(failure_reason, '') as failure_reason, gateway_txn_ref,
           coalesce({{ safe_numeric('gateway_fee_inr') }}, 0) as gateway_fee_inr, _loaded_at
    from {{ source('raw','payments') }}
),
by_id as ({{ dedupe('typed', 'payment_id', '_loaded_at desc') }}),
by_ref as ({{ dedupe('by_id', 'gateway_txn_ref', 'payment_id', rn='_rn_ref') }})
select p.payment_id, p.order_id, p.attempt_no, p.payment_at, p.payment_at::date as payment_date,
       coalesce(pm.payment_method, 'Unknown') as payment_method, p.gateway,
       -- marketplace settlement feed reports paise
       case when p.gateway = 'mkt_settlement' then p.amount_raw / 100.0 else p.amount_raw end as amount_inr,
       p.amount_raw, p.payment_status, p.payment_status = 'success' as is_success, p.failure_reason,
       p.gateway_txn_ref, p.gateway_fee_inr
from by_ref p
left join {{ ref('payment_method_mapping') }} pm on pm.raw_value = p.payment_method_raw
