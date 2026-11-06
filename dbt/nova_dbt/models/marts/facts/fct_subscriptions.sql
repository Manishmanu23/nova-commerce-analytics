-- grain: ONE ROW PER NOVA PLUS SUBSCRIPTION
select subscription_id, customer_id, plan_type, start_at, end_at, start_at::date as start_date, status, fee_inr,
       round((extract(epoch from (coalesce(end_at, '{{ var("data_end_date") }}'::timestamp) - start_at)) / 86400 / 30.44)::numeric, 1)
           as months_active
from {{ ref('stg_subscriptions') }}
