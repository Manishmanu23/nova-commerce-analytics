-- grain: one row per session with the deepest funnel steps reached.
with e as (
    select session_id,
           count(*)                                               as n_events,
           bool_or(event_name = 'product_view')                   as has_product_view,
           bool_or(event_name = 'add_to_cart')                    as has_add_to_cart,
           bool_or(event_name = 'begin_checkout')                 as has_begin_checkout,
           bool_or(event_name = 'payment_attempt')                as has_payment_attempt,
           bool_or(event_name = 'purchase')                       as has_purchase,
           count(*) filter (where event_name = 'payment_attempt') as n_payment_attempts
    from {{ ref('stg_funnel_events') }}
    group by 1
)
select s.*, coalesce(e.n_events, 0) as n_events,
       coalesce(e.has_product_view, false) as has_product_view, coalesce(e.has_add_to_cart, false) as has_add_to_cart,
       coalesce(e.has_begin_checkout, false) as has_begin_checkout,
       coalesce(e.has_payment_attempt, false) as has_payment_attempt,
       coalesce(e.has_purchase, false) as has_purchase, coalesce(e.n_payment_attempts, 0) as n_payment_attempts
from {{ ref('stg_web_sessions') }} s
left join e using (session_id)
