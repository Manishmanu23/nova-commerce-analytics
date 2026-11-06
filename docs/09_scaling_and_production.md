# Scaling and Productionising

## From portfolio to production

| Concern | Portfolio (this repo) | Production |
|---|---|---|
| Warehouse | Postgres 16 in Docker | Snowflake / BigQuery / Redshift. The dbt models port with adapter macros |
| Orchestration | Makefile | Airflow / Dagster: sensors on file arrival, retries, SLAs, backfills |
| Loads | Full-file COPY with hash idempotency | CDC (Debezium/Fivetran) into raw; dbt **incremental** models with a `unique_key` and a 14-day lookback for late data |
| SCD2 | Built from CDC rows | dbt **snapshots** where the source only sends current state |
| Tests | dbt tests + scorecard | Same, plus alerting (Slack/PagerDuty) on `error`, and trend alerts on `warn` counts |
| BI | Power BI Import on `metrics_*`/`mart_*` | Incremental refresh, deployment pipelines, RLS by region/brand, certified dataset |
| Copilot | Template or LLM + validator | Same design, plus logging of every question/evidence/answer, a human feedback loop, and the eval suite in CI |
| Secrets | `.env` | Vault / cloud secret manager |
| Lineage | dbt docs | dbt docs + catalog (DataHub/OpenMetadata) |

## Scaling to 1 billion rows

1. **Partition** facts by month (`order_date`), and **cluster** or sort by `customer_id` for per-customer windows.
2. **Incremental everything.** Keep per-customer order sequences in a state table instead of re-windowing history.
3. **Pre-aggregate** (`metrics_daily`, `fct_customer_monthly`). BI never scans raw facts.
4. **BRIN indexes** on time columns (Postgres) or micro-partition pruning (Snowflake).
5. **Push sessionisation** of billions of events to Spark or streaming. dbt keeps the business logic on the output.
6. **Cost controls:** warehouse auto-suspend, query tags, and a model runtime budget in CI.

## Monitoring the pipeline

- **Freshness:** dbt source freshness plus DQ check T1.
- **Volume:** row counts per batch vs a same-weekday baseline (the same robust z used for metrics).
- **Schema:** contract check at ingestion. Drift is logged in the audit table.
- **Quality:** dbt test trend, DQ scorecard. **Metric drift:** the anomaly system on governed metrics, plus a weekly check that the distributions (PSI) of key inputs (AOV, basket size, payment mix) are stable.
- **Business SLAs:** the executive dashboard is ready by 09:00 IST. If it isn't, a banner shows yesterday's data.

## If the source changes

- **New column:** added automatically to raw (non-breaking) and logged. Staging ignores it until it is modelled.
- **Removed or renamed required column:** the file is rejected at ingestion. Downstream keeps the last good data, and the owner is alerted.
- **New label value** (for example a new channel): it falls into 'unknown', the `accepted_values` test warns, and someone adds a seed mapping row.
- **Semantics change** (for example, amounts start arriving net of tax): only reconciliation tests (K1/K2) and anomaly detection can catch this. That is why they exist.
