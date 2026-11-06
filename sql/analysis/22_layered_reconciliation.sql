/* =====================================================================================
Q22  Layered reconciliation: raw -> staging -> mart row counts and revenue
-------------------------------------------------------------------------------------
BUSINESS QUESTION  "Finance says revenue is X, your dashboard says Y." Where does the difference come from?
WHY IT WORKS       Each layer's number is computed side by side; every gap is explained by a named rule
                   (duplicates removed, invalid dates, test orders, non-completed orders, refunds, coupons).
WHY THIS MATTERS   Trust is earned by being able to walk from the source total to the reported total.
===================================================================================== */
with raw as (
    select count(*) as raw_rows, count(distinct order_id) as raw_distinct_orders,
           sum(case when subtotal_inr ~ '^[0-9.]+$' then subtotal_inr::numeric end) as raw_subtotal_incl_dups
    from raw.orders
),
stg as (select count(*) as stg_orders, sum(subtotal_inr) as stg_subtotal from staging.stg_orders),
f as (
    select count(*) filter (where not is_valid_order_date) as invalid_date_orders,
           count(*) filter (where is_internal_test) as test_orders,
           count(*) filter (where not is_completed) as not_completed_orders,
           sum(items_gross_revenue_inr) filter (where not is_countable) as excluded_gross,
           sum(gross_revenue) as gross_revenue, sum(coupon_discount) as coupons, sum(return_refunds) as refunds,
           sum(net_revenue) as net_revenue
    from marts.fct_orders
)
select s.step_no, s.step, s.value from raw, stg, f
cross join lateral (values
    (1, 'raw order rows (incl. re-sent duplicates)',   raw.raw_rows::numeric),
    (2, 'distinct order_ids in raw',                   raw.raw_distinct_orders),
    (3, 'staging orders (after de-dup)',               stg.stg_orders),
    (4, ' - orders with invalid dates',                f.invalid_date_orders),
    (5, ' - internal test orders',                     f.test_orders),
    (6, ' - cancelled / payment-failed orders',        f.not_completed_orders),
    (7, 'raw subtotal INCL duplicates (INR)',          round(raw.raw_subtotal_incl_dups)),
    (8, 'staging subtotal after de-dup (INR)',         round(stg.stg_subtotal)),
    (9, 'governed gross revenue (INR)',                round(f.gross_revenue)),
    (10, ' - coupon discounts',                        round(f.coupons)),
    (11, ' - return refunds',                          round(f.refunds)),
    (12, 'governed NET revenue (INR)',                 round(f.net_revenue))
) s(step_no, step, value)
order by s.step_no;
