# ADR-001: PostgreSQL as the warehouse
**Status:** accepted. **Decision:** PostgreSQL 16 in Docker.
**Why:** it is free, runs locally, and is reproducible by any reviewer in one command. It has real warehouse features: window functions, `EXPLAIN ANALYZE`, indexes, partitioning, BRIN. SQL skills transfer directly to Snowflake and BigQuery.
**Alternatives:** DuckDB (excellent for local analytics, but I wanted server semantics, concurrency and indexes to demonstrate optimisation). Snowflake/BigQuery (cost and signup friction for reviewers; the scaling doc maps every design choice to them).
**Consequences:** it is a row store, so large scans are slower than on columnar engines. That is mitigated by pre-aggregation and would be solved by the cloud warehouse in production.
