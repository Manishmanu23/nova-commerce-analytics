# Data Quality Framework

## Principles

1. **Detect → correct or flag → disclose.** Every known defect is handled in code and stays visible on the DQ page. Nothing is silently dropped.
2. **Severity reflects decision risk.** `error` stops the pipeline (for example, duplicate primary keys in a mart, or revenue not reconciling). `warn` monitors known, mitigated source defects.
3. **Tolerances, not perfection.** Each check has warn and fail thresholds tied to business impact.

## Layered controls

| Layer | Control | Examples |
|---|---|---|
| Ingestion | Data contract (required columns), SHA-256 idempotency, per-file transaction, audit log, schema-drift logging | Missing `order_id` column → file rejected. Re-run → "already loaded" |
| Staging (dbt) | uniqueness, not-null, accepted values, relationships, ranges, custom tests | `accepted_values` on channel after seed mapping. `within_data_window` on order dates. `not_before` (delivered ≥ ordered) |
| Marts (dbt) | Grain tests, SCD2 overlap, FK to dims, reconciliation | `unique_combination_of_columns`, `assert_no_fanout_order_items`, `assert_scd2_no_overlap`, `sum_reconciles` |
| Metrics (dbt) | Cross-surface reconciliation, ranges, unexpected shift | `metrics_daily` net revenue = `fct_orders` = `fct_order_items`. `assert_no_unexpected_metric_shift` |
| Experiments (dbt) | Sample-ratio mismatch | `assert_experiment_sample_ratio` (χ² > 10.83) |
| Source behaviour (dbt) | Raw duplicate rate by day | `assert_raw_duplicate_rate_by_day` catches the 2025-03-18 re-sent batch |
| Python | DQ scorecard (17 threshold checks + dbt pass rate), anomaly raw-layer scan | `python -m nova.dq.scorecard` |

## Defect register (what the source does wrong, and what we do about it)

| Defect | Detected by | Handling | Residual risk |
|---|---|---|---|
| OMS retry duplicates, full-day re-sent batch | `source_row_count`, raw dup-rate test, U1 | Latest `_extracted_at` wins | None for revenue. Raw counts differ from governed counts (explained in `sql/analysis/22`) |
| Webhook-replay payments | `unique` on `gateway_txn_ref`, U2 | De-dup by txn ref | — |
| Marketplace amounts in paise | reconciliation test K1 | ÷100 for `mkt_settlement` | New gateways need the same rule, so there is a contract note |
| UTC timestamps | design | `to_ist()` macro | — |
| Invalid dates (1970, 2031, delivered < ordered) | `within_data_window`, `not_before` | `is_reportable = false`. Delivery time set to NULL | About 0.2% of orders excluded |
| Messy labels | `accepted_values` post-mapping | Seed mapping tables | New labels fall into 'unknown' and the test warns |
| Missing product cost | `max_null_rate` | Category-median imputation + flag | Margin estimate on about 2% of versions |
| Missing customer geo | `max_null_rate` | 'Unknown' member | State analysis loses about 4% |
| Orphan products / customers | `relationships` (warn) | Unknown members, revenue kept | Product P&L misses about 0.2% |
| Negative refund sign | `not_negative` after fix, V3 | `abs()` + flag | — |
| Negative marketing spend | design | **Kept**: legitimate credit notes, netted | — |
| Late refunds | arrival-lag analysis, T2 | `is_refund_mature` flag, provisional badge | Last 3 weeks of refund rate understated |
| Bot traffic | anomaly (sessions spike) + V5 | `is_bot` flag, excluded from conversion | New bot signatures |
| Test orders | email-domain rule | `is_reportable = false` | New test domains |
| Legacy customers (history not migrated) | design | Excluded from cohort/LTV/retention | Conservative: some true 2024 first-timers who signed up in 2023 are excluded |

## Scorecard

See `reports/data_quality_scorecard.md` (generated). On the full run the overall score is **86.2 / 100, "fit with caveats"**. Every warning is a known, mitigated defect. Consistency (reconciliations) scores 100.

## Operating model (production)

- dbt `error` failures block the downstream publish, and Power BI keeps yesterday's data with a banner.
- `warn` counts are trended (`dq.dbt_test_results` is append-only). A warn count that jumps more than 3x day over day pages the data owner.
- Each defect class has an owner: OMS team (duplicates), payments (paise, replays), CRM (geo), ERP (cost).
