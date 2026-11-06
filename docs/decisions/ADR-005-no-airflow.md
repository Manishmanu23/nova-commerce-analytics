# ADR-005: Makefile instead of Airflow
**Decision:** a Makefile orchestrates one daily batch of about 8 steps.
**Why:** an orchestrator's value (scheduling, retries, backfills, a UI) grows with the number of jobs and teams. Here it would add Docker services and DAG code without changing any outcome. The `make` targets map 1:1 to future Airflow tasks.
**Revisit when:** there are more than 20 jobs, multiple sources on different schedules, SLAs, or a need for backfills.
