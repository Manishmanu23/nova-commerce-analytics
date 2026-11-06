/* =====================================================================================
Q23  Late-arriving data: how many refunds arrive after N days, and how incomplete is last month?
-------------------------------------------------------------------------------------
BUSINESS QUESTION  Can we trust December's refund rate today?
WHY IT WORKS       arrival_lag_days = extracted_at - refund_at. The cumulative distribution tells us what % of
                   refunds are known N days after they happen; refund timing after delivery adds more delay.
DECISION RULE      Mark refund-rate periods as provisional until ~95% of refunds have typically arrived
                   (metrics_daily.is_refund_mature). The dashboard shows a "provisional" badge instead of a
                   falsely low number.
===================================================================================== */
with r as (
    select refund_id, order_date, refund_date, arrival_lag_days, days_after_delivery, batch_id
    from marts.fct_refunds where is_return_refund
)
select 'arrival lag (refund -> our warehouse)' as measure,
       round(percentile_cont(0.5) within group (order by arrival_lag_days)::numeric, 1) as p50_days,
       round(percentile_cont(0.95) within group (order by arrival_lag_days)::numeric, 1) as p95_days,
       count(*) filter (where batch_id = '2026-01-12') as arrived_in_late_batch
from r
union all
select 'order date -> refund date',
       round(percentile_cont(0.5) within group (order by (refund_date - order_date))::numeric, 1),
       round(percentile_cont(0.95) within group (order by (refund_date - order_date))::numeric, 1),
       null
from r;
