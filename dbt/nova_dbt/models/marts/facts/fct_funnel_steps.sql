-- grain: ONE ROW PER (SESSION, FUNNEL STEP REACHED). Non-bot sessions only.
-- Long format lets BI tools draw a funnel with "step" as a dimension without 6 separate measures.
select f.session_id, f.session_date, f.device_type, f.geo_id, f.traffic_channel, f.app_version,
       s.step_number, s.step_name
from {{ ref('fct_sessions') }} f
cross join lateral (values
    (1, 'session_start',   true),
    (2, 'product_view',    f.has_product_view),
    (3, 'add_to_cart',     f.has_add_to_cart),
    (4, 'begin_checkout',  f.has_begin_checkout),
    (5, 'payment_attempt', f.has_payment_attempt),
    (6, 'purchase',        f.has_purchase)
) as s(step_number, step_name, reached)
where s.reached and not f.is_bot
