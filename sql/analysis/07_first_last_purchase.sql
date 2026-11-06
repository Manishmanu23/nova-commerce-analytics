/* =====================================================================================
Q07  First and last purchase per customer: first category, last category, lifetime span
-------------------------------------------------------------------------------------
BUSINESS QUESTION  Which entry categories create long-lived customers?
WHY IT WORKS       FIRST_VALUE / LAST_VALUE over a per-customer ordered window.
GOTCHA             LAST_VALUE needs an explicit frame (ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING);
                   the default frame ends at the CURRENT ROW, so LAST_VALUE would just return the current row.
ALTERNATIVE        Postgres DISTINCT ON (customer_id) … ORDER BY customer_id, order_at is faster for first-only.
AT SCALE           Computing both in one window pass avoids two separate sorts.
===================================================================================== */
with lines as (
    select i.customer_id, i.order_date, i.category,
           row_number() over (partition by i.order_id order by i.gross_revenue desc) as rk  -- main category of the order
    from marts.fct_order_items i where i.is_countable and i.customer_id is not null
),
o as (select * from lines where rk = 1),
fl as (
    select distinct customer_id,
           first_value(category)  over w as first_category,
           last_value(category)   over w as last_category,
           first_value(order_date) over w as first_order_date,
           last_value(order_date)  over w as last_order_date
    from o
    window w as (partition by customer_id order by order_date
                 rows between unbounded preceding and unbounded following)
)
select first_category, count(*) as customers,
       round(avg(last_order_date - first_order_date), 1) as avg_lifetime_days,
       round(avg(case when last_category <> first_category then 1.0 else 0 end), 3) as share_cross_category
from fl group by 1 order by avg_lifetime_days desc;
