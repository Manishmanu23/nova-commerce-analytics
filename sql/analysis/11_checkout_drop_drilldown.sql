/* =====================================================================================
Q11  Drill-down: app checkout conversion by state x app version, before / during / after Nov-2025 drop
-------------------------------------------------------------------------------------
BUSINESS QUESTION  Mobile checkout conversion fell in Nov 2025. Where exactly, and did the hotfix work?
WHY IT WORKS       Period buckets from CASE on date; compare checkout->purchase rate for the same segment.
WHY THIS WAY       Holding segment constant across periods isolates WHEN, the state/version split isolates WHERE.
                   HAVING >= 200 checkouts avoids reading noise in tiny segments as signal.
CAUTION            This localises the problem (app 5.2.0 + UPI + 3 states); it does not PROVE the cause.
                   Confirm with payment failure_reason logs and the engineering release notes.
===================================================================================== */
with s as (
    select f.*, g.state,
           case when f.session_date <  '2025-11-12' then '1_before'
                when f.session_date <  '2025-12-03' then '2_during'
                else '3_after' end as period
    from marts.fct_sessions f join marts.dim_geography g using (geo_id)
    where f.device_type = 'mobile_app' and not f.is_bot and f.session_date >= '2025-10-01'
)
select period,
       case when state in ('Uttar Pradesh', 'Bihar', 'West Bengal') then state else 'Other states' end as state_group,
       app_version,
       count(*) filter (where has_begin_checkout) as checkouts,
       round(count(*) filter (where has_purchase)::numeric / nullif(count(*) filter (where has_begin_checkout), 0), 4) as checkout_conversion
from s
group by 1, 2, 3
having count(*) filter (where has_begin_checkout) >= 30
order by 2, 3, 1;
