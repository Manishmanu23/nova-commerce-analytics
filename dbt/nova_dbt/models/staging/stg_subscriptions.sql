-- grain: one row per Nova Plus subscription
select subscription_id, customer_id, plan_type, {{ to_ist('start_ts') }} as start_at, {{ to_ist('end_ts') }} as end_at,
       status, {{ safe_numeric('fee_inr') }} as fee_inr
from ({{ dedupe(source('raw','subscriptions'), 'subscription_id', '_loaded_at desc') }}) d
