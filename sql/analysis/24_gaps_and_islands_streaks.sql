/* =====================================================================================
Q24  Gaps & islands: longest streak of consecutive active months per customer
-------------------------------------------------------------------------------------
BUSINESS QUESTION  How many customers form a monthly habit, and how long do habits last?
WHY IT WORKS       For consecutive months, (month_index - row_number) is constant -> it identifies an "island".
WHY THIS WAY       Classic pattern that avoids recursive CTEs; runs in one sort per customer.
===================================================================================== */
with a as (
    select customer_id, month,
           (extract(year from month) * 12 + extract(month from month))::int as month_idx
    from marts.fct_customer_monthly where is_active and not is_legacy_customer
),
g as (
    select customer_id, month_idx - row_number() over (partition by customer_id order by month_idx) as island
    from a
),
streaks as (select customer_id, island, count(*) as streak_len from g group by 1, 2),
best as (select customer_id, max(streak_len) as longest_streak from streaks group by 1)
select longest_streak, count(*) as customers,
       round(count(*)::numeric / sum(count(*)) over (), 4) as share
from best group by 1 order by 1;
