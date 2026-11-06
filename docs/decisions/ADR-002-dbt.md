# ADR-002: dbt for transformations
**Decision:** dbt-core with staging → intermediate → marts → metrics layers.
**Why:** version-controlled SQL, a dependency graph (lineage), tests next to models, generated documentation, and environment targets (dev/ci). Stored procedures offer none of these, and notebooks can't be tested or reviewed.
**Consequences:** it adds a tool to learn. Business logic lives in SQL files that reviewers can read in PRs.
