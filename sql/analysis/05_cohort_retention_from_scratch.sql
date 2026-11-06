/* =====================================================================================
Q05  Monthly cohort retention matrix built from the order fact (no helper tables)
-------------------------------------------------------------------------------------
BUSINESS QUESTION  Of customers acquired in month M, what share buys again in month M+1, M+2, …?
WHY IT WORKS       1) first order month per customer (MIN)   2) distinct active (customer, month) pairs
                   3) month offset = age   4) active / cohort size.
WHY THIS WAY       * DISTINCT (customer, month) before counting: a customer with 3 orders in a month is 1 active.
                   * Cohort size taken from offset 0 of the SAME cohort so rows are comparable.
                   * Cohort = FIRST ORDER month, not signup month (signups that never buy would dilute it).
VALIDATION         Offset 0 must be 100% (dbt test assert_retention_month0_is_100pct).
EDGE CASE          The latest cohorts have fewer observable months - blank cells mean "not yet observable",
                   not 0% retention. Never average across rows without weighting by cohort size.
AT SCALE           Materialise (customer, month) activity incrementally (fct_customer_monthly) and
                   aggregate that - it is ~100x smaller than the order fact.
===================================================================================== */
with orders as (
    select customer_id, order_month from marts.fct_orders
    where is_countable and customer_id is not null and not is_orphan_customer
      and not is_legacy_customer      -- pre-2024 history not migrated: their true cohort is unknown
),
firsts as (select customer_id, min(order_month) as cohort_month from orders group by 1),
activity as (select distinct customer_id, order_month from orders),
aged as (
    select f.cohort_month, a.customer_id,
           (extract(year from age(a.order_month, f.cohort_month)) * 12
            + extract(month from age(a.order_month, f.cohort_month)))::int as month_offset
    from activity a join firsts f using (customer_id)
),
counts as (
    select cohort_month, month_offset, count(*) as active_customers from aged group by 1, 2
)
select c.cohort_month, c.month_offset, c.active_customers,
       first_value(c.active_customers) over (partition by c.cohort_month order by c.month_offset) as cohort_size,
       round(c.active_customers::numeric
             / first_value(c.active_customers) over (partition by c.cohort_month order by c.month_offset), 4) as retention
from counts c
where c.month_offset <= 12
order by 1, 2;
