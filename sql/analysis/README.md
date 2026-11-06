# SQL analysis library

Each file opens with a header: **business question → why it works → why it is written this way → performance → how it scales**. All files run against the built warehouse (`psql -f <file>`).

| # | Topic | Techniques |
|---|---|---|
| 01 | Monthly revenue & CM, MoM / YoY | CTE, gap-free month spine, `LAG(…,12)`, pp vs % |
| 02 | Profit waterfall | `CROSS JOIN LATERAL (VALUES …)` unpivot |
| 03 | Volume vs value decomposition | `LAG`, exact additive decomposition |
| 04 | Rolling 7/28-day metrics | window frames, ratio re-aggregation (right vs wrong) |
| 05 | Cohort retention from scratch | `MIN` cohort, `age()`, `FIRST_VALUE` |
| 06 | Inter-purchase time, repeat rate | `LAG` per customer, `percentile_cont`, maturity |
| 07 | First / last purchase | `FIRST_VALUE`/`LAST_VALUE` frame gotcha, `DISTINCT ON` |
| 08 | RFM segmentation | `NTILE`, tie handling, share of CM |
| 09 | LTV vs CAC by channel | maturity filter, cohort-matched CAC |
| 10 | Funnel by device | `COUNT(*) FILTER`, bot exclusion |
| 11 | Checkout drop drill-down | period buckets, segment isolation, `HAVING` noise floor |
| 12 | Top-N products per category | `DENSE_RANK` vs `RANK` vs `ROW_NUMBER` |
| 13 | Brand refund trend | `LAG` over partitions, `RANK` movement |
| 14 | Payment success by segment | benchmark on the same row, z-score screening |
| 15 | Anomaly screen in SQL | same-weekday median/MAD robust z |
| 16 | Campaign economics | CAC vs 90-day CM payback |
| 17 | Discount depth vs retention | bucketing, observational caveat |
| 18 | Membership naive vs stratified | selection bias demonstration |
| 19 | 90-day churn as-of | range joins, right-censoring guard |
| 20 | New vs returning mix | window share |
| 21 | Experiment readout in SQL | SRM χ², CI for difference of proportions |
| 22 | Layered reconciliation | raw → staging → governed walk |
| 23 | Late-arriving refunds | lag percentiles, provisional logic |
| 24 | Gaps & islands | consecutive active months |
| 25 | Pareto concentration | running `SUM`, `PERCENT_RANK` |
| 26 | Contribution to change | share of change by dimension |
| 27 | AOV distribution | mean vs median vs governed AOV |

Performance case studies: [`../performance/`](../performance).
