/* PERFORMANCE CASE STUDY 2 - physical design for the order fact at scale
   (DDL shown for PostgreSQL; the same ideas map to Snowflake clustering keys / BigQuery partitioning.) */

-- 1) B-tree indexes that match real access paths (created by dbt `indexes` config on fct_orders)
--    * order_id (unique)             -> point lookups, joins from items/payments/refunds
--    * order_date                    -> date-range dashboards
--    * customer_id                   -> cohort/LTV window functions & per-customer drill-through
create index if not exists ix_fct_orders_customer_date on marts.fct_orders (customer_id, order_date);

-- 2) BRIN index: tiny (KBs) and ideal for append-only, time-ordered facts
create index if not exists brin_fct_sessions_date on marts.fct_sessions using brin (session_date);

-- 3) Declarative range partitioning by month (what you'd do past ~100M rows)
--    Partition pruning means "last 90 days" touches 3-4 partitions instead of the whole table,
--    and old partitions can be detached/archived cheaply.
create table if not exists marts.fct_orders_partitioned (like marts.fct_orders including defaults)
    partition by range (order_date);
do $$
declare m date;
begin
  for m in select generate_series('2024-01-01'::date, '2025-12-01'::date, interval '1 month')::date loop
    execute format('create table if not exists marts.fct_orders_p%s partition of marts.fct_orders_partitioned
                    for values from (%L) to (%L)', to_char(m, 'YYYYMM'), m, (m + interval '1 month')::date);
  end loop;
end $$;
create table if not exists marts.fct_orders_p_default partition of marts.fct_orders_partitioned default;

-- 4) Check the planner prunes partitions
explain (costs off)
select sum(net_revenue) from marts.fct_orders_partitioned where order_date >= '2025-10-01';

-- 5) Keep statistics fresh after big loads (bad estimates => bad join strategies)
analyze marts.fct_orders;

-- cleanup of the demo table (comment out to keep)
drop table if exists marts.fct_orders_partitioned cascade;
