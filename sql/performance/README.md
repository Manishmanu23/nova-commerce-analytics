# Query performance notes

| # | Problem | Fix | Measured (15k-customer dataset) |
|---|---|---|---|
| 1 | Correlated `EXISTS` against a view, evaluated per order (`SubPlan` loop) | Set-based join computed once, then a hash join | **24.8 s → 0.18 s** (query), model build 36 s → 1 s |
| 2 | 1M-row session view with regex casts joined on a computed key (no index possible) | Materialise `stg_web_sessions` / `stg_funnel_events` as tables + index on `session_id` | Downstream models 9 s → 2 s |
| 3 | Rolling / cohort metrics recomputed from the fact on each dashboard click | Pre-aggregate into `metrics_daily`, `fct_customer_monthly` | 730-row and ~150k-row tables instead of 1M+ |
| 4 | Ratio metrics averaged at the wrong grain | Store numerator + denominator, recompute | Correctness fix, not speed |

## How I'd scale this to 1 billion rows

1. **Incremental models.** Turn `stg_orders`, `fct_orders`, `fct_sessions` and `fct_funnel_steps` into dbt `incremental` models with `unique_key` and a **lookback window** (for example, the last 14 days get reprocessed every run). The lookback catches late-arriving refunds and status changes.
2. **Partition by date, cluster by the join key.** In Postgres: monthly range partitions plus BRIN indexes. In Snowflake: clustering on `order_date`. In BigQuery: `PARTITION BY order_date CLUSTER BY customer_id`.
3. **Pre-aggregate for BI.** Power BI reads `metrics_*` and `mart_*` tables (thousands of rows), never the raw facts. Use DirectQuery only on aggregates; use Import plus incremental refresh for everything else.
4. **Avoid sort-heavy window functions on the full fact.** Compute per-customer sequences incrementally (new orders only), and store `customer_order_number`.
5. **Move the heaviest sessionisation work upstream** (streaming or Spark) if event volume reaches billions per day. dbt still owns business logic on the sessionised output.
6. **Measure before and after.** Keep `EXPLAIN (ANALYZE, BUFFERS)` outputs in PRs for any model that runs longer than 1 minute.
