/* =====================================================================================
Q19  90-day inactivity churn rate as of each month start
-------------------------------------------------------------------------------------
BUSINESS QUESTION  What share of recently active customers are we losing?
DEFINITION         Active base at date D = customers with >= 1 completed order in [D-90, D).
                   Churned = active-base customers with no order in [D, D+90).
WHY THIS WAY       Churn in non-subscription commerce must be DEFINED (no cancel event). The 90-day window is
                   ~p80 of inter-purchase time (Q06). Only months with a full 90-day forward window are shown
                   (otherwise recent months look artificially "churny" - right censoring).
PERFORMANCE        Range join (customer, date window). An index on fct_orders(customer_id, order_date) turns it
                   into index range scans; metrics_monthly materialises the result.
===================================================================================== */
with co as (
    select distinct customer_id, order_date from marts.fct_orders
    where is_countable and customer_id is not null and not is_orphan_customer
),
ms as (select generate_series('2024-04-01'::date, '2025-10-01'::date, interval '1 month')::date as d),
base as (
    select distinct ms.d, co.customer_id from ms join co on co.order_date >= ms.d - 90 and co.order_date < ms.d
),
fwd as (
    select distinct b.d, b.customer_id from base b
    join co on co.customer_id = b.customer_id and co.order_date >= b.d and co.order_date < b.d + 90
)
select b.d as as_of, count(*) as active_base, count(*) - count(f.customer_id) as churned,
       round(1 - count(f.customer_id)::numeric / count(*), 4) as churn_rate_90d
from base b left join fwd f using (d, customer_id)
where b.d + 90 <= '2026-01-01'
group by 1 order by 1;
