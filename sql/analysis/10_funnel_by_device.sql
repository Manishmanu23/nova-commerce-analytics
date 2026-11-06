/* =====================================================================================
Q10  Funnel step conversion by device (monthly)
-------------------------------------------------------------------------------------
BUSINESS QUESTION  Where in the funnel do we lose users, and is it device-specific?
WHY IT WORKS       COUNT(*) FILTER (WHERE step reached) per step; step-to-step = step_n / step_(n-1).
WHY THIS WAY       * Session-based ("closed") funnel: a purchase counts only if its session also had checkout.
                   * Bots excluded (is_bot) - the 2025-05-22 bot spike would otherwise crater desktop conversion.
                   * FILTER is one pass; 5 separate subqueries would scan 5 times.
AT SCALE           mart_funnel_daily already holds these counts at (date, device, state, channel, version) grain.
===================================================================================== */
select date_trunc('month', session_date)::date as month, device_type,
       count(*) as sessions,
       round(count(*) filter (where has_add_to_cart)::numeric / count(*), 4)                                         as view_to_cart,
       round(count(*) filter (where has_begin_checkout)::numeric / nullif(count(*) filter (where has_add_to_cart), 0), 4) as cart_to_checkout,
       round(count(*) filter (where has_purchase)::numeric / nullif(count(*) filter (where has_begin_checkout), 0), 4)    as checkout_to_purchase,
       round(count(*) filter (where has_purchase)::numeric / count(*), 4)                                            as session_conversion
from marts.fct_sessions
where not is_bot
group by 1, 2
order by 1, 2;
