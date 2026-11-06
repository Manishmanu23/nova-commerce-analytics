/* PERFORMANCE CASE STUDY 1 - "is this order placed by a Nova Plus member?"
   First version of int_orders__enriched used a correlated EXISTS against a VIEW (stg_subscriptions),
   inside a model that also joined a 1M-row VIEW (stg_web_sessions) on a computed key.
   Measured on the 15k-customer dataset: model build 36.2 s -> 1.0 s after the fix.          */

-- BEFORE: correlated subquery, re-evaluated per order against a view that re-casts text every time
explain (analyze, buffers, costs off, timing off)
select o.order_id,
       exists (select 1 from staging.stg_subscriptions sb
               where sb.customer_id = o.customer_id and o.order_at >= sb.start_at
                 and o.order_at < coalesce(sb.end_at, '9999-12-31')) as is_member_order
from staging.stg_orders o;

-- AFTER: set-based join, computed once, then a hash join back to orders
explain (analyze, buffers, costs off, timing off)
with member_orders as (
    select distinct o.order_id
    from staging.stg_orders o
    join staging.stg_subscriptions sb
      on sb.customer_id = o.customer_id and o.order_at >= sb.start_at
     and o.order_at < coalesce(sb.end_at, '9999-12-31')
)
select o.order_id, mo.order_id is not null as is_member_order
from staging.stg_orders o left join member_orders mo using (order_id);

/* Second fix: stg_web_sessions / stg_funnel_events materialised as TABLES with an index on session_id
   (dbt config: materialized='table', indexes=[...]). A view over TEXT columns with regex casts cannot
   use an index on the join key, so every downstream join re-parsed 1M rows.

   LESSONS
   * Views are free to build but you pay on every read; materialise what many models read.
   * Correlated subqueries are fine for tiny outer sets, pathological for large ones - rewrite as joins.
   * Always read EXPLAIN ANALYZE: look for SubPlan loops, Seq Scans on big tables inside loops, and
     estimated vs actual row counts that differ by 10x+ (stale statistics -> ANALYZE).            */
