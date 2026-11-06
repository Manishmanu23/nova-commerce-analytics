# Data

- `landing/<batch_date>/*.csv`: generated source extracts (gitignored; `make generate`). Batch `2026-01-01` is the main extract, and `2026-01-12` holds late-arriving refunds.
- `sample/landing/`: the small CI dataset (`make sample`).
- `ground_truth/`: the planted scenarios, the defect log and row counts. **Only the generator and the evaluation code read these files.** Analysis code must never read them.

Row counts for the default run (30k registered customers): about 33k customer versions, 60k orders, 93k order lines, 60k payments, 7.8k refunds, 1.69M sessions, 2.77M funnel events, 4.8k tickets, 11k experiment assignments.
