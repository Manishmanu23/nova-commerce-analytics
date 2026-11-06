/* =====================================================================================
Q14  Payment success rate by method x state with a significance guard
-------------------------------------------------------------------------------------
BUSINESS QUESTION  Which payment segments are failing more than normal?
WHY IT WORKS       Segment rate vs overall rate for the same month, with a two-proportion z-score so small
                   segments with noisy rates are not flagged.
WHY THIS WAY       Window AVG over the whole month gives the benchmark on the same row (no self-join).
                   |z| > 3 is a screening threshold for MANY simultaneous comparisons (multiple-testing aware).
===================================================================================== */
with p as (
    select date_trunc('month', p.payment_date)::date as month, p.payment_method, g.state, p.is_success
    from marts.fct_payments p join marts.dim_geography g using (geo_id)
    where p.is_prepaid_attempt and p.is_reportable and p.payment_date >= '2025-09-01'
),
seg as (
    select month, payment_method, state, count(*) as attempts, avg(is_success::int) as success_rate
    from p group by 1, 2, 3
),
bench as (select month, avg(is_success::int) as overall from p group by 1)
select s.month, s.payment_method, s.state, s.attempts, round(s.success_rate, 4) as success_rate,
       round(b.overall, 4) as overall_rate,
       round((s.success_rate - b.overall) / sqrt(b.overall * (1 - b.overall) / s.attempts), 2) as z_score
from seg s join bench b using (month)
where s.attempts >= 50
order by z_score
limit 20;
