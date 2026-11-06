# 10. Interview Preparation: NovaCommerce Decision Intelligence & Revenue Analytics Platform

This document lists interview questions specific to this project, each with a model answer. Every number quoted comes from the full simulated run: 30,000 registered customers, about 60k orders, 1.69M sessions, 2.77M funnel events, 2024-01-01 to 2025-12-31. All results are **simulated**. Say so every time you quote one.

## How to use this

- **Do not memorise the answers.** Learn the structure: *decision → why → trade-off → evidence in the repo*. Interviewers probe with "why?" two or three times. The answers here are written so that each "why" has an answer.
- **Point to files.** A good answer ends with "you can see it in `dbt/nova_dbt/models/marts/facts/fct_orders.sql`" or "the test is `assert_retention_month0_is_100pct.sql`". It shows you built the thing and did not just read about it.
- **Always say "simulated" or "synthetic"** when you quote a result. Never let a number sound like real business impact.
- **Answer at the right altitude.** A hiring manager for a Data Analyst role wants the business framing first ("the cheapest campaign was the least profitable"). An analytics engineer panel wants grain, tests and idempotency. Open with one sentence at the level they asked, then offer to go deeper.
- **Rehearse aloud** the Project-defense section (Section 6). Those are the questions that separate candidates.
- Section order: SQL (30), Python (20), Power BI / DAX (20), Statistics (15), Business case (15), Project defense (30), then red-flag answers to avoid.

Key files referenced below:

| Area | Path |
|---|---|
| Generator (scenarios, defects) | `python/nova/generator/` (`scenarios.py`, `defects.py`) |
| Ingestion | `ingestion/load_raw.py`, `ingestion/schemas/` |
| dbt macros | `dbt/nova_dbt/macros/casting.sql`, `tests.sql` |
| dbt singular tests | `dbt/nova_dbt/tests/` |
| Facts / dims / marts | `dbt/nova_dbt/models/marts/` |
| Metrics layer | `dbt/nova_dbt/models/metrics/` |
| Analysis SQL | `sql/analysis/01_...sql` to `27_...sql` |
| Performance | `sql/performance/` |
| Analytics | `python/nova/analytics/` |
| Anomaly detection | `python/nova/anomaly/` |
| DQ scorecard | `python/nova/dq/scorecard.py` |
| Simulator | `python/nova/simulator/engine.py` |
| Copilot | `python/nova/copilot/` |
| Reports | `reports/*.md` |
| Tests | `tests/` (17 pytest tests) |

---

## 1. SQL (30 questions)

### SQL-1. What is the grain of `fct_orders`, and why does it matter?

One row per order. It is an accumulating snapshot: placed, paid, shipped, then delivered or cancelled. Grain decides which measures are additive and which joins are safe. Order-level measures like shipping fee, coupon and gateway fee live here. Line-level measures like COGS and item gross live in `fct_order_items`. If I joined orders to items and summed shipping fee, I would multiply it by the number of lines. The singular test `assert_no_fanout_order_items.sql` guards that: the sum of item gross must equal order gross.

### SQL-2. Why are the governed measure columns in `fct_orders` pre-zeroed?

The rule "count only completed, reportable orders" is easy to forget. Reportable means not a test order, not an invalid date and not a duplicate. So I compute `is_countable = is_completed and is_reportable` once in dbt. Every governed column (`gross_revenue`, `net_revenue`, `contribution_margin`, `completed_orders`) is `case when is_countable then ... else 0 end`. A plain `SUM(net_revenue)` from any tool is then always the governed number. The unfiltered amounts are kept with an `_inr` suffix, such as `items_gross_revenue_inr`, for reconciliation. The trade-off is a wider table, which is cheap.

```sql
case when is_countable then items_gross_revenue_inr - coupon_discount_inr - return_refund_inr_raw else 0 end as net_revenue
```

### SQL-3. How do you remove OMS retry duplicates in staging?

I use latest-record-wins deduplication with `row_number()`. The `dedupe` macro in `casting.sql` wraps this pattern:

```sql
select * from (
  select *, row_number() over (partition by order_id order by _loaded_at desc, _source_file desc) as _rn
  from raw.orders
) d where _rn = 1;
```

About 1.2% of order rows were retries. The full-day re-sent batch on 2025-03-18 collapses the same way, because the order ids repeat. I keep `source_row_count` on `fct_orders` so the duplication stays visible and is not silently hidden.

### SQL-4. Raw revenue spikes on 2025-03-18 but governed revenue does not. How do you prove both facts?

I run a layered reconciliation (`sql/analysis/22_layered_reconciliation.sql`). It compares, by day: raw row count and amount, then after dedupe, after test-order and invalid-date exclusion, then governed `metrics_daily.net_revenue`. On 2025-03-18 the raw layer roughly doubles and the deduped layer is normal. Separately, the singular test `assert_raw_duplicate_rate_by_day.sql` warns when the daily duplicate rate passes its threshold. The raw-layer anomaly scan flagged that day at a 99% duplicate rate. The spike should exist in raw and must not exist in governed metrics. Showing both is the proof.

### SQL-5. Write a cohort retention query from scratch.

This is `sql/analysis/05_cohort_retention_from_scratch.sql`. The core:

```sql
with first_order as (
  select customer_id, date_trunc('month', min(order_at))::date as cohort_month
  from marts.fct_orders
  where is_countable and not is_legacy_customer and customer_id is not null
  group by 1
),
activity as (
  select distinct customer_id, date_trunc('month', order_at)::date as active_month
  from marts.fct_orders where is_countable
)
select f.cohort_month,
       (extract(year from age(a.active_month, f.cohort_month)) * 12
        + extract(month from age(a.active_month, f.cohort_month)))::int as month_n,
       count(distinct a.customer_id) as active_customers,
       count(distinct a.customer_id)::numeric
         / max(count(distinct a.customer_id)) over (partition by f.cohort_month) as retention
from first_order f join activity a using (customer_id)
group by 1, 2 order by 1, 2;
```

Legacy customers are excluded because their first order in the data is not their real first order. The mart version (`mart_cohort_retention`) stores additive counts (cohort size, active customers). BI then recomputes the rate and never averages it.

### SQL-6. How would you compute month-over-month and year-over-year revenue?

I use `lag()` over a monthly aggregate (`01_monthly_revenue_mom_yoy.sql`, materialised as `metrics_monthly`):

```sql
select month, net_revenue,
       net_revenue / nullif(lag(net_revenue, 1)  over (order by month), 0) - 1 as mom,
       net_revenue / nullif(lag(net_revenue, 12) over (order by month), 0) - 1 as yoy
from (select date_trunc('month', date_day)::date as month, sum(net_revenue) as net_revenue
      from metrics.metrics_daily group by 1) m;
```

This depends on a gap-free month spine. `metrics_daily` is built off `dim_date`, so months with no sales still exist and `lag(…,12)` really is 12 months back. In the simulated run, Nov 2025 was −33.6% MoM and Dec 2025 was +15.7% MoM and +72% YoY.

### SQL-7. Rolling 7-day and 28-day averages: what is the trap?

Two traps. First, missing days: `rows between 6 preceding` counts rows, not days. Without a date spine, a missing day turns a 7-day window into an 8-day one. `metrics_daily` is spine-based, so rows equal days. Second, ratios: a rolling conversion rate must be `sum(purchase_sessions)/sum(sessions)` over the window, not the average of daily rates (`04_rolling_averages.sql`).

```sql
sum(purchase_sessions) over w / nullif(sum(sessions) over w, 0) as conv_7d
window w as (order by date_day rows between 6 preceding and current row)
```

### SQL-8. How do you decompose a revenue change into drivers?

`03_revenue_change_decomposition.sql` splits Δ revenue into orders × AOV. Volume effect = ΔOrders × AOV_prev. Price effect = ΔAOV × Orders_prev. Interaction = ΔOrders × ΔAOV. For a segment view (`26_contribution_to_change_by_state.sql`), each state's contribution is its own Δ divided by the total Δ. For rates, the Copilot `breakdown` tool does a rate + mix decomposition. Rate effect = Δrate × previous share. Mix effect = Δshare × previous rate. That shows whether conversion fell because the segments got worse or because traffic shifted toward low-converting segments.

### SQL-9. Build a profit waterfall from gross revenue to contribution margin after marketing.

`02_profit_waterfall.sql` unpivots summed components into ordered steps: Gross revenue, − coupons, − return refunds = Net revenue, − net COGS = Gross profit, + shipping fees collected, − shipping cost, − gateway fees, − marketplace commission = Contribution margin, − marketing = CM after marketing.

```sql
select * from (values
  (1, 'Gross revenue', (select sum(gross_revenue) from m)),
  (2, 'Coupons', -(select sum(coupon_discount) from m)), ...
) v(step, label, amount) order by step;
```

CM after marketing is only valid at date, channel or campaign grain. Marketing spend cannot be allocated to a product or customer without an attribution assumption, so I do not show it at those grains.

### SQL-10. Write an RFM segmentation in SQL.

`08_rfm_segmentation.sql`: compute recency (days since the last countable order, as of 2025-12-31), frequency (countable orders) and monetary value (net revenue) per non-legacy buyer. Score each with `ntile(5) over (order by ...)`. Recency is ordered descending, so recent customers get 5. Then map score combinations to named segments (Champions, At risk, Hibernating). Two details matter. Frequency has heavy ties at 1, so `ntile` splits identical values across buckets arbitrarily. I either use fixed thresholds for F or accept that and document it. And the as-of date must be fixed, not `now()`, so results are reproducible.

### SQL-11. Top-N products per category.

`12_top_n_products_per_category.sql`:

```sql
select * from (
  select p.category, p.product_name, sum(oi.net_revenue) as net_rev,
         dense_rank() over (partition by p.category order by sum(oi.net_revenue) desc) as rnk
  from marts.fct_order_items oi join marts.dim_product p using (product_version_key)
  group by 1, 2
) t where rnk <= 5;
```

`dense_rank` keeps ties. `row_number` would drop them arbitrarily. Because `dim_product` is SCD2, I group by product attributes that do not change, or by the current version. Grouping by version key would split one product's revenue across price versions.

### SQL-12. How is the SCD2 point-in-time join written?

```sql
left join int_products__scd2 p
  on p.product_id = oi.product_id
 and o.order_at >= p.valid_from and o.order_at < p.valid_to
```

The interval is half-open (`>=` and `<`), so a timestamp exactly on a boundary matches one version, not two. `valid_to` for the current row is a far-future date, not NULL, so the predicate stays simple and sargable. The first customer version is valid from 1900-01-01, so orders before the first CDC change still match. `assert_scd2_no_overlap.sql` checks that versions do not overlap, and the no-fan-out test catches any double match.

### SQL-13. How do you test that SCD2 intervals do not overlap?

```sql
select a.customer_id
from int_customers__scd2 a
join int_customers__scd2 b
  on a.customer_id = b.customer_id and a.customer_version_key <> b.customer_version_key
 and a.valid_from < b.valid_to and b.valid_from < a.valid_to;
```

Any row returned fails the test. A cheaper equivalent uses `lead(valid_from) over (partition by customer_id order by valid_from)` and checks `valid_to = next_valid_from`, which also catches gaps.

### SQL-14. Exact duplicate CDC rows: how did they affect SCD2?

Duplicate change rows would create zero-length or duplicate versions, and the point-in-time join would then fan out. I deduplicated CDC rows on (customer_id, changed_at, tracked attributes) before building versions. I also collapse consecutive rows where the tracked attributes (city/geo) did not change. That is a gaps-and-islands step, so a no-op update does not create a new version.

### SQL-15. What is a gaps-and-islands problem, and where did you use it?

It means grouping consecutive rows that share a state. `24_gaps_and_islands_streaks.sql` finds customers' consecutive active-month streaks: `month_index − row_number() over (partition by customer_id order by month)` is constant within a streak. I used the same idea to collapse no-op SCD2 changes, and it is how you would find outage windows, such as consecutive days with payment success below a threshold.

### SQL-16. How do you handle UTC timestamps when the business reports in IST?

Sources emit UTC. The `to_ist` macro converts them:

```sql
(case when col ~ '^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$'
      then (col::timestamp at time zone 'UTC') at time zone 'Asia/Kolkata' end)
```

An order at 20:00 UTC is 01:30 IST the next day. Without conversion, evening orders land on the wrong day, and festival-day revenue shifts. The regex guard turns malformed values into NULL, which a test catches, instead of failing the whole model.

### SQL-17. Why is the raw layer all TEXT?

Ingestion must never fail because a source sent `"N/A"` in a numeric column or a date like `2031-02-30`. Loading as TEXT makes ingestion lossless: every byte the source sent is preserved and auditable. Typing happens in dbt staging with `safe_numeric`, `safe_int`, `safe_date` and `to_ist`. Bad values become NULL and generic tests (`max_null_rate`, `within_data_window`) flag them. The cost is that casting logic lives in staging, which is where it belongs.

### SQL-18. How did you find invalid dates (1970, 2031, delivered before ordered)?

Custom generic tests. `within_data_window` checks that dates fall within the reporting window plus tolerance. `not_before` checks one column against another (`delivered_at` not before `order_at`). Rows that fail are not deleted. They get `is_valid_order_date = false` and so `is_reportable = false`, so they are excluded from governed measures but stay countable in DQ. Those tests are configured as warn because the defects are known and mitigated.

### SQL-19. How do you normalise inconsistent labels like "FB / Meta / facebook"?

`norm(col) = lower(trim(col))`, then a left join to a seed mapping (`channel_mapping.csv`, `category_mapping.csv`, `payment_method_mapping.csv`). Unmapped values fall through to `'unmapped'`, and an `accepted_values` test fails. A new raw label therefore breaks the build loudly instead of creating a new "channel" in the dashboard. Seeds are version-controlled, so every mapping change is reviewed.

### SQL-20. Marketplace payments were in paise. How did you detect and fix it?

The marketplace payment amounts were about 100× the order totals for the same orders. I fixed it in staging: `case when source_system = 'marketplace' then amount / 100.0 else amount end`. The reconciliation test `assert_prepaid_collections_match_orders.sql` compares collected payment amounts to order totals for prepaid orders. It would catch a regression, or a new source with a different unit.

### SQL-21. How do you dedupe webhook-replay payments?

Payment gateways retry webhooks, so the same transaction arrives several times with different row ids but the same `gateway_txn_ref`. `fct_payments` dedupes on `gateway_txn_ref`, keeping the first received. Its grain is one row per payment attempt, so a failed attempt followed by a successful retry is two legitimate rows. That is different from two copies of the same attempt. Getting this wrong inflates the failure rate, the success rate, or collections, depending on which rows were replayed.

### SQL-22. One refund source sends negative amounts. How do you handle signs?

I standardise in staging: `abs(amount)` for the source known to send negatives, with the sign convention documented (refunds positive, subtracted in the metric). Marketing spend is different. Negative spend rows are legitimate credit notes, so they are kept and netted. A `not_negative` test is applied to refunds and deliberately not to spend. The general rule: know why a value is negative before you "fix" it.

### SQL-23. Late-arriving refunds: how do they affect the refund rate?

Refunds arrive weeks after the order. A second refund batch landed on 2026-01-12. I measure the refund rate by order date: refunds on orders placed in period P divided by gross revenue of period P. That is the correct cohort view, but recent periods are understated until refunds mature. So the last ~21 days are flagged provisional. `23_late_arriving_refunds.sql` shows the refund-lag distribution and how much the rate for each month moved after the late batch. The refund-date view exists too, for finance cash reporting, and it is labelled differently.

### SQL-24. Write the payment success rate by segment for the app release incident.

`14_payment_success_by_segment.sql`:

```sql
select date_trunc('week', payment_date) as wk, device_type, state, payment_method,
       count(*) filter (where is_success)::numeric / count(*) as success_rate, count(*) as attempts
from marts.fct_payments p join marts.dim_geography g using (geo_id)
where is_prepaid_attempt and is_reportable
group by grouping sets ((1, device_type), (1, device_type, state), (1, device_type, payment_method));
```

In the simulated run, national success barely moved. Within `mobile_app` it fell from 89.1% to 76.9%. Inside that: Uttar Pradesh 91.5%→54.4%, West Bengal 91.4%→54.9%, Bihar 89.7%→48.1%, and UPI 93.1%→66.8%. Always show `attempts` next to a rate, so small segments do not look alarming.

### SQL-25. Write a robust z-score anomaly query in SQL.

`15_anomaly_detection_robust_z.sql` compares each day with the median of the same weekday over the previous 8 weeks, scaled by MAD:

```sql
with base as (
  select d.date_day, d.net_revenue,
         percentile_cont(0.5) within group (order by h.net_revenue) as med
  from metrics.metrics_daily d
  join metrics.metrics_daily h
    on extract(dow from h.date_day) = extract(dow from d.date_day)
   and h.date_day between d.date_day - 56 and d.date_day - 7
  group by 1, 2
) ...
-- z = (x - median) / (1.4826 * MAD)
```

The median and MAD are not dragged by the spikes you are trying to detect. The Python version also masks sale days out of the baseline.

### SQL-26. Pareto concentration: what share of revenue comes from the top 20% of customers?

`25_pareto_customer_concentration.sql`: rank customers by net revenue, then compute a cumulative share with `sum(net_rev) over (order by net_rev desc) / sum(net_rev) over ()`, and a customer percentile with `percent_rank()` or `ntile(100)`. Exclude the 'unknown' guest member and B2B bulk buyers. One bulk buyer can distort the curve.

### SQL-27. Churn "as of" a date: how do you avoid look-ahead and incomplete-window bias?

`19_churn_as_of.sql`. Churned at date D means the customer was active in the 90 days before D and inactive in the 90 days after D. I only compute it for D values with a full 90-day forward window, so no D after 2025-10-02 for data ending 2025-12-31. Otherwise the recent periods show inflated churn simply because the future has not happened yet.

### SQL-28. How did you compute 90-day repeat rate by acquisition campaign without bias?

Only mature customers count: those whose first order was at least 90 days before the data end. For a customer acquired on 2025-12-15, "no second order within 90 days" is unknown, not zero.

```sql
select campaign_id,
       avg(case when second_order_at <= first_order_at + interval '90 days' then 1.0 else 0 end) as repeat_90d
from mart_customer_ltv where is_mature_90d group by 1;
```

`mart_customer_ltv` carries `is_mature_90d/180d/365d` flags for exactly this. In the simulated run, the Aug–Oct 2025 cohorts repeated at 42–44% against 55–57% for Jun–Jul.

### SQL-29. Your slowest query took 24.8 s. What was wrong, and how did you fix it?

Recorded in `sql/performance/01_correlated_exists_vs_join.sql`. A correlated `EXISTS` against a view ran as a `SubPlan` for every order. Because the view had regex casts, no index could be used, so it re-evaluated the view per outer row. I rewrote it as a set-based pre-aggregation joined once (a hash join). On the 15k-customer development dataset, the query went from 24.8 s to 0.18 s and the model build from 36 s to 1 s. I also materialised the large staging views (`stg_web_sessions`, `stg_funnel_events`) as tables indexed on `session_id`. I diagnosed it with `EXPLAIN (ANALYZE, BUFFERS)`, not by guessing.

### SQL-30. How would you check that an experiment exposure table has no post-assignment leakage?

`fct_experiment_exposures` has one row per experiment × customer. `orders_in_window`, `converted` and `net_revenue` count only orders from `assigned_at` up to the experiment end date. `pre_period_orders` and `pre_period_net_revenue` cover the 28 days before assignment and feed CUPED and balance checks. I verify with an independent recomputation:

```sql
with recomputed as (
  select e.experiment_id, e.customer_id,
         count(o.order_id) filter (where o.order_at >= e.assigned_at
                                     and o.order_at <  x.end_date + 1) as orders_post
  from marts.fct_experiment_exposures e
  join marts.dim_experiment x using (experiment_id)
  left join marts.fct_orders o on o.customer_id = e.customer_id and o.is_countable
  group by 1, 2
)
select count(*) from recomputed r
join marts.fct_experiment_exposures e using (experiment_id, customer_id)
where r.orders_post <> e.orders_in_window;   -- must be 0
```

A balance check helps too. Pre-period revenue should be similar across arms. If treatment looks better before it was treated, something leaked. That sits alongside `assert_experiment_sample_ratio.sql`, which runs a chi-square SRM test on assignment counts per arm and flagged EXP-2025-02.

---

## 2. Python (20 questions)

### PY-1. Why generate synthetic data instead of using a Kaggle dataset?

Public e-commerce datasets are already clean, have no ground truth for "why" questions, and lack the linked tables I needed: sessions, funnel, payments, refunds, spend, experiments, subscriptions, CDC. The seeded generator in `python/nova/generator/` produces 16 source tables with **planted scenarios** (S1–S6) and **deliberate defects**. I can therefore validate my methods against a known answer. Did the anomaly system find the app-release incident? Did matching recover the true membership effect? The analysis code never reads the ground truth. It is used only in evaluation. The trade-off is realism: the distributions are my assumptions, and I say so.

### PY-2. How do you make the generator reproducible?

One seed flows through a single `numpy.random.Generator`, and configuration lives in `config.py`. With the same seed and customer count (`make generate CUSTOMERS=30000`), the files come out byte-identical, so SHA-256 hashes match and ingestion correctly skips them on re-run. `tests/test_generator.py` asserts determinism and that planted defects are present at their configured rates. Reproducibility is what lets CI run the full pipeline on a 1,500-customer sample and get stable results.

### PY-3. Walk me through the ingestion script.

`ingestion/load_raw.py`, per file:

1. Compute the SHA-256. If `raw._ingestion_audit` already has a success row for that hash, skip it (idempotent).
2. Check the header against `ingestion/schemas/contracts.yml`. Missing required columns reject the file and log it.
3. Create the raw table as all-TEXT if absent. New columns in the file are schema drift: `ALTER TABLE ADD COLUMN`, logged in the audit row.
4. `COPY` into a temp stage table, then `INSERT ... SELECT` into raw with `_batch_id` and `_source_file`. `_loaded_at` defaults to now().
5. Write the audit row and commit. Each file is one transaction: all rows or none.

A partial unique index on `file_hash where status = 'success'` makes a double load impossible even under concurrency.

### PY-4. Why COPY and not pandas `to_sql`?

`COPY` streams the file straight into Postgres, with no row-by-row inserts and no DataFrame in memory. `to_sql` either issues many INSERTs or needs `method='multi'` batching, and it infers types, which contradicts the all-TEXT raw design. For 1.69M sessions and 2.77M funnel events, COPY is an order of magnitude faster and uses constant memory. I stream the file in 1 MB chunks.

### PY-5. What does "idempotent" mean here, and how do you test it?

Running the pipeline twice gives the same result as running it once. Ingestion is idempotent by file hash. dbt models are rebuilt deterministically from raw, and dedupe happens in staging, so even a re-sent file with a different hash, such as the 2025-03-18 batch, collapses to the same governed numbers. Test: run `make ingest` twice and assert that raw row counts and `metrics_daily` totals do not change. Then drop in a duplicate batch and assert that governed revenue does not change while `assert_raw_duplicate_rate_by_day` warns.

### PY-6. Why do some analyses live in Python and not SQL?

The rule: **aggregation and business logic go in SQL/dbt, statistical inference goes in Python.** Welch t-tests, bootstrap CIs, CUPED, Holm/BH corrections, coarsened exact matching, STL decomposition, ETS forecasting and Monte Carlo simulation are awkward or impossible in SQL. Python reads from governed marts and metrics, never raw, so it cannot disagree with the dashboard on the base numbers.

### PY-7. How is the experiment analysis implemented?

`python/nova/analytics/experiments.py` handles each experiment in this order:

1. SRM chi-square on arm counts against `planned_split`. If p < 0.001, the verdict is INVALID and nothing else is interpreted.
2. Primary metric (purchase rate): difference in proportions with a 95% CI and relative lift.
3. Revenue per user: Welch t-test (`welch`) plus a bootstrap CI (`boot_diff_ci`), because revenue is zero-inflated and skewed.
4. CUPED (`cuped`) using `pre_period_net_revenue` as the covariate.
5. Balance check: standardised mean difference (`smd`) on pre-period metrics.
6. Power and MDE, then secondary metrics and subgroups with Holm and BH corrections.
7. A decision rule that maps the results to SHIP, SHIP WITH MONITORING, INCONCLUSIVE or INVALID.

### PY-8. Show me CUPED.

```python
def cuped(y, x):
    theta = np.cov(y, x, ddof=1)[0, 1] / np.var(x, ddof=1)
    return y - theta * (x - x.mean())
```

θ is estimated on the pooled sample, both arms together, so it does not depend on treatment. The adjusted metric has the same expected difference and lower variance, by a factor of about 1 − ρ² where ρ is the correlation between pre-period and in-experiment revenue. For a new-ish customer base with sparse pre-period purchases ρ is small, so the gain is modest, and I report both adjusted and unadjusted.

### PY-9. How does the bootstrap CI work, and why use it?

Resample each arm with replacement 2,000 times, compute the difference in means each time, and take the 2.5th and 97.5th percentiles. Revenue per user is mostly zeros with a long right tail, so the normal approximation behind a t-interval can be off at moderate n. The bootstrap makes no distributional assumption. I report both. When they disagree materially, the bootstrap wins and I say why.

### PY-10. How does the anomaly detector work?

`python/nova/anomaly/detectors.py` has three detectors:

- `seasonal_robust_z`: expected value = median of the same weekday over the previous 8 weeks, with sale days masked out. Deviation is relative. Noise is 1.4826 × the rolling median absolute relative deviation over 91 days, lagged one day so today cannot mask itself.
- `stl_residual_z`: a robust STL decomposition with period 7, used as a cross-check. An incident needs agreement or a strong single signal.
- `rate_binomial_z` for rates: expected rate = pooled same-weekday rate (Σnum / Σden, never the mean of ratios). z uses the binomial standard error, corrected for over-dispersion with φ estimated from recent squared z values (quasi-binomial) and floored at 1.

`run.py` then merges consecutive flags into incidents, classifies them, runs the weekly segment scan and drills down.

### PY-11. Why the over-dispersion correction?

With 2,000+ sessions a day, the binomial SE of conversion is tiny, so ordinary day-to-day variation (weather, a marketing email) produces |z| > 3 constantly. Real traffic is over-dispersed relative to binomial. Estimating φ from recent history and dividing by √φ gives z values with the intended false-positive rate. Without it, the incident list would be mostly noise and nobody would read it.

### PY-12. How are incidents classified?

`classify()` in `anomaly/run.py`, in priority order:

1. `expected_seasonal`: the date falls on a known sale or festival flag in `dim_date`.
2. `data_quality`: evidence of a data issue, such as a bot share of 90% on 2025-05-22 or a raw duplicate spike.
3. `one_off_outlier`: a single order explains most of the deviation (B2B bulk orders).
4. `business_signal`: whatever is left.

In the simulated run, 23 top-line incidents split into 15 expected_seasonal, 4 one_off_outlier, 1 data_quality and 3 business_signal. The 3 business signals are my false-positive budget. I would rather investigate 3 a year than miss the real one.

### PY-13. How was the app-release incident (S2) actually found?

Not by the top-line detector. National payment success moved too little to cross the threshold, which is the "averages hide problems" lesson. The weekly **segment scan** (`segment_scan`) runs the rate z-test on each value of each dimension (device, state, payment method, channel). It flagged `device_type=mobile_app`: payment success 89.1% → 76.9% (−13.7%, |z| 7.8, 11–30 Nov 2025, simulated). `segment_drill` then ranked sub-segments inside it: Uttar Pradesh, West Bengal and Bihar all fell to around 48–55%, and UPI to 66.8%. The incident card estimates about 64 extra failed orders over 3 weeks, roughly ₹1.5 lakh of order value at risk (simulated).

### PY-14. How is the forecast selected?

`python/nova/analytics/forecast.py` works on weekly net revenue. Four candidates: naive, 4-week mean, seasonal naive × growth, and damped-trend ETS on log revenue. I ran a rolling-origin backtest over 26 origins with a 13-week horizon and scored WAPE and bias. Damped ETS on log won with WAPE 15.8% and bias −13%. The 13-week total is ₹2.27 Cr, labelled FORECAST. The −13% bias means it under-forecasts, mostly around festive peaks it cannot anticipate. I state that next to the number instead of hiding it.

### PY-15. Why not Prophet or an ML model for the forecast?

Two years of weekly data is 104 points, with festivals that move between years. A model with many parameters would overfit, and the backtest is what decides, not fashion. Damped ETS is transparent, fast and hard to break. The honest improvement is a festival-calendar regressor, such as ETS or ARIMA with holiday dummies from `dim_date`. I would test it in the same backtest harness and adopt it only if WAPE improves.

### PY-16. How does the decision simulator work?

`python/nova/simulator/engine.py`. A `Baseline` dataclass is estimated from observed Jul–Dec 2025 data: customers, monthly churn, orders per customer, AOV, discount rate, refund rate, COGS %, variable cost per order, marketing spend, CAC, organic new customers. A `Scenario` dataclass holds levers: `retention_pp`, `conversion_pct`, `aov_pct`, `cac_pct`, `refund_pp`, `discount_pp`, `marketing_pct`. `project()` runs a 12-month customer-flow model. `monte_carlo()` samples baseline parameters from their observed variability (500 draws) to produce P10/P90. Every input is labelled observed, assumption, forecast or estimate.

### PY-17. What are the simulator's biggest limitations?

- **No demand elasticity.** A +3% price does nothing to conversion unless the user says so. I force users to state the conversion effect (the example uses −2%).
- Levers are independent. There is no interaction between discounting and retention unless both are set.
- Baseline parameters come from six months, including the festive peak and the Social Blitz period.
- The P10/P90 band reflects parameter noise, not structural uncertainty in the model.

This is why the output ranks options, such as the retention programme at +₹6.8L CM after marketing against the price rise at +₹2.7L (simulated). It is not a promise.

### PY-18. How is the DQ scorecard computed?

`python/nova/dq/scorecard.py` runs 17 threshold checks: duplicate rates, null rates, invalid dates, orphan keys, freshness, reconciliation. It adds the dbt test pass rate collected by `collect_dbt_results.py`. Each check maps to a dimension: Uniqueness, Completeness, Validity, Referential integrity, Timeliness, Consistency. Pass = 1, warn = 0.8 (a known, mitigated defect), fail = 0. Dimension scores average into an overall score. The simulated run scored 86.2/100, "fit with caveats": Uniqueness 80, Completeness 80, Validity 84, Referential integrity 80, Timeliness 90, Consistency 100.

### PY-19. How does the Copilot validator work?

`python/nova/copilot/validator.py`:

1. Build the allowed-number set from every Evidence object's display values and raw values. Formatting is normalised, so ₹96.3L and 96.3 both match.
2. Every number token in the answer must be in that set. Small integers ≤ 10, years, dates, versions and methodology constants like "90-day" are exempt.
3. Every snake_case token must be a certified metric name from the catalogue or a whitelisted dimension value.
4. Every paragraph containing numbers must cite an evidence id like `[E2]`.

If validation fails, the LLM answer is discarded and the deterministic template answer is returned.

### PY-20. What do the 17 pytest tests cover?

`tests/test_generator.py` (determinism, defect rates), `test_anomaly_detectors.py` (a planted spike is detected, a seasonal day is not, over-dispersion lowers z), `test_planner.py` (synonym mapping, refusals for NPS/GMV/out-of-window, month parsing), `test_copilot_validator.py` (invented number, invented metric, uncited paragraph and re-rounded number rejected; clean answer accepted) and `test_simulator.py` (a zero-lever scenario equals the baseline, levers move results in the right direction). CI runs them with ruff and dbt build on the 1,500-customer sample.

---

## 3. Power BI / DAX (20 questions)

### PBI-1. Describe the report.

Six pages, designed from a written spec with the DAX in the repo. I built the `.pbix` myself.

1. **Executive overview:** net revenue, CM, CM after marketing, orders, AOV, with MoM and YoY.
2. **Profitability:** waterfall from gross revenue to CM after marketing.
3. **Customers and retention:** cohort heatmap, repeat rate, LTV:CAC.
4. **Acquisition and channels:** CAC, ROAS, LTV:CAC by channel and campaign.
5. **Funnel and payments:** conversion, checkout drop-off, payment success by segment.
6. **Data quality and anomalies:** DQ scorecard, incident list, provisional-period flags.

It reads marts and metrics tables, never raw facts at full grain where an aggregate exists.

### PBI-2. How is the model structured?

A star schema. Facts (`fct_orders`, `fct_sessions`, `fct_marketing_spend`, `metrics_daily`) sit in the centre. Dimensions (`dim_date`, `dim_channel`, `dim_geography`, `dim_product`, `dim_customer`, `dim_campaign`) filter them through single-direction one-to-many relationships. `dim_channel` is conformed: orders, sessions and spend all map to the same channel keys through a dbt seed. One slicer therefore filters revenue, traffic and spend consistently, which is what makes CAC and ROAS by channel possible.

### PBI-3. Write the base measures.

```DAX
Net Revenue      = SUM ( fct_orders[net_revenue] )
Gross Revenue    = SUM ( fct_orders[gross_revenue] )
Contribution Margin = SUM ( fct_orders[contribution_margin] )
Completed Orders = SUM ( fct_orders[completed_orders] )
```

No `CALCULATE` filter on status is needed, because the governed columns are already zero for non-countable orders. That removes the most common source of "the dashboard and the SQL don't match".

### PBI-4. How do you write ratio measures correctly?

Always divide summed components, never average a stored ratio:

```DAX
CM % = DIVIDE ( [Contribution Margin], [Net Revenue] )
Conversion Rate = DIVIDE ( SUM ( metrics_daily[purchase_sessions] ), SUM ( metrics_daily[sessions] ) )
AOV = DIVIDE ( SUM ( fct_orders[aov_order_value] ), SUM ( fct_orders[aov_orders] ) )
```

`DIVIDE` returns BLANK on a zero denominator instead of an error. `metrics_daily` stores numerators and denominators for exactly this reason. `AVERAGE(daily_conversion)` would weight a 200-session day the same as a 20,000-session day.

### PBI-5. Why is AOV built from `aov_order_value` and `aov_orders` instead of revenue / orders?

The governed AOV excludes B2B bulk orders (any line with quantity ≥ 20). One bulk order can move daily AOV by double digits and trigger false anomalies. The dbt model pre-computes the AOV-eligible numerator and denominator, and the measure just divides them. The exclusion is in the metric catalogue, so everyone uses the same definition.

### PBI-6. Time intelligence: what do you need, and show MoM.

A proper date table: `dim_date`, marked as the date table, contiguous, one row per day, with the Indian fiscal year (Apr–Mar) and festival flags. Then:

```DAX
Net Revenue PM  = CALCULATE ( [Net Revenue], DATEADD ( dim_date[date_day], -1, MONTH ) )
Net Revenue MoM % = DIVIDE ( [Net Revenue] - [Net Revenue PM], [Net Revenue PM] )
Net Revenue PY  = CALCULATE ( [Net Revenue], SAMEPERIODLASTYEAR ( dim_date[date_day] ) )
Net Revenue FYTD = TOTALYTD ( [Net Revenue], dim_date[date_day], "03-31" )
```

The `"03-31"` year-end argument gives Indian fiscal YTD. Without a marked date table, time intelligence functions fail silently or behave oddly on the auto date hierarchy. I disable auto date/time.

### PBI-7. Why a separate Unknown member in dimensions?

Guest orders, orphan customers (late-arriving dimension) and missing geo all map to an explicit `'unknown'` or `'-1'` key. Without it, facts with no matching dimension row appear as a (Blank) category in Power BI, or disappear from filtered visuals, and totals stop matching the sum of the parts. With an Unknown member, the rows are visible and labelled, and the DQ page can show how big "Unknown" is.

### PBI-8. How do you handle SCD2 dimensions in Power BI?

The fact carries the version key (`customer_version_key`, `product_version_key`) chosen at the point-in-time join in dbt. So "revenue by customer city" means the city at the time of the order, which is correct for historical geography. For "current city" analysis, I add a `current_city` attribute to every version row in dbt instead of doing time-travel logic in DAX. DAX should not reproduce the join logic.

### PBI-9. Bidirectional filters: when, and why did you avoid them?

I avoided them. Bidirectional filtering creates ambiguous paths once there are several facts sharing dimensions. For example, date → orders ↔ customer → sessions can filter one fact through another in unexpected ways, and it hurts performance. When I need a dimension filtered by a fact, such as a slicer showing only campaigns with spend, I use a measure-based visual filter or `CROSSFILTER` inside one specific measure:

```DAX
Customers with Orders =
CALCULATE ( DISTINCTCOUNT ( fct_orders[customer_id] ),
            CROSSFILTER ( fct_orders[customer_version_key], dim_customer[customer_version_key], BOTH ) )
```

### PBI-10. How is CAC computed in DAX, given spend and customers are in different facts?

Both facts connect to the conformed `dim_date` and `dim_channel`, so:

```DAX
Acquisition Spend = CALCULATE ( SUM ( fct_marketing_spend[spend_inr] ), fct_marketing_spend[is_acquisition_spend] = TRUE () )
Paid New Customers = SUM ( metrics_daily[paid_new_customers] )
CAC = DIVIDE ( [Acquisition Spend], [Paid New Customers] )
Blended CAC = DIVIDE ( [Acquisition Spend], SUM ( metrics_daily[new_customers] ) )
```

Acquisition spend excludes email/CRM. I show paid CAC and blended CAC side by side, because leadership often means blended while marketing means paid.

### PBI-11. How would you show CM after marketing without misleading?

Only at date, channel and campaign grain, because spend has no product or customer key. On visuals sliced by product or city, the measure returns BLANK:

```DAX
CM After Marketing =
IF ( ISFILTERED ( dim_product[category] ) || ISFILTERED ( dim_geography[state] ),
     BLANK (),
     [Contribution Margin] - SUM ( fct_marketing_spend[spend_inr] ) )
```

A tooltip explains why. Allocating spend to products would show numbers that look precise and are really assumptions.

### PBI-12. How did you implement the what-if analysis?

Power BI what-if parameters (a generated table plus `SELECTEDVALUE`) for discount change, churn change and conversion change:

```DAX
Scenario CM =
VAR d = SELECTEDVALUE ( 'Discount Change'[Discount Change], 0 )
RETURN [Contribution Margin] - d * [Gross Revenue]
```

This is only a sensitivity view. The full 12-month scenario model with Monte Carlo bands lives in the Python simulator, and its output table is imported. I would not rebuild a customer-flow model in DAX.

### PBI-13. How would you implement row-level security?

For example, category managers see only their categories and state heads only their states. Create roles filtering the dimension, not the fact:

```DAX
-- Role: StateHead, table dim_geography
dim_geography[state] = LOOKUPVALUE ( user_access[state], user_access[email], USERPRINCIPALNAME () )
```

It uses dynamic RLS from a mapping table, so there is no role per state. Filters propagate one-directionally to facts. Test with "View as role". One caveat: aggregated tables without the state key (like `metrics_daily`) are not secured by that filter, so they must either be excluded from restricted roles or carry the key.

### PBI-14. Import or DirectQuery?

Import. Marts and metrics are small (`metrics_daily` is 730 rows, monthly marts are thousands, and `fct_orders` about 60k), so Import gives the fastest visuals and full DAX. DirectQuery would push every visual interaction to Postgres and limit DAX. At production scale I would use a composite model: Import for aggregates and dimensions, DirectQuery or incremental refresh for the detailed fact, with aggregation tables so most visuals never touch the detail.

### PBI-15. How would you set up incremental refresh?

Define `RangeStart` and `RangeEnd` datetime parameters. Filter `fct_orders[order_at]` with `>= RangeStart` and `< RangeEnd` in Power Query so the filter folds to SQL. Configure a policy to store 3 years and refresh the last 30 days. The 30-day window matches the data reality: late refunds and status changes arrive within ~21 days, so a 1-day refresh would leave stale refund numbers. Detect data changes on a `_loaded_at` or `updated_at` column to skip unchanged partitions.

### PBI-16. How do you show that the last ~21 days of refund rate are provisional?

`metrics_daily` carries an `is_refund_mature` flag: the date is at least 21 days before the data end date. The refund rate visual draws immature periods with a dashed line or lighter colour, driven by measures:

```DAX
Refund Rate = DIVIDE ( SUM ( metrics_daily[return_refund_amount] ), SUM ( metrics_daily[gross_revenue] ) )
Refund Rate (Mature) = CALCULATE ( [Refund Rate], metrics_daily[is_refund_mature] = TRUE () )
```

A subtitle states "last 21 days provisional". Otherwise someone will celebrate a refund rate that is falling only because refunds have not arrived yet.

### PBI-17. The Power BI total does not match your SQL. How do you debug it?

In order:

1. Check the filter context: slicers, page filters, and hidden visual-level filters.
2. Check relationships: an inactive relationship, a many-to-many, or unmatched keys going to (Blank).
3. Check measure logic: averaging ratios, `SUM` of a pre-computed ratio column, or a `CALCULATE` removing a filter.
4. Check refresh time against the dbt build time.

I run the same query in SQL on `metrics_daily` for the same filters. Because governed columns are pre-zeroed and ratios are component-based, the usual cause is a relationship or a filter, not a definition.

### PBI-18. How do you build the cohort retention heatmap?

From `mart_cohort_retention`: rows = cohort month, columns = months since first order, values = a ratio measure:

```DAX
Retention = DIVIDE ( SUM ( mart_cohort_retention[active_customers] ), SUM ( mart_cohort_retention[cohort_size] ) )
```

This uses a matrix with conditional-format background colours. Because the mart stores additive counts, selecting several cohorts gives a correctly weighted retention, not an average of percentages. Legacy customers are excluded upstream, and the month-0 = 100% test guarantees the first column.

### PBI-19. How would you handle Indian number formatting (lakh/crore)?

Use a format string measure or a dynamic format string:

```DAX
Net Revenue (Display) =
VAR v = [Net Revenue]
RETURN SWITCH ( TRUE (),
    ABS ( v ) >= 1e7, FORMAT ( v / 1e7, "₹#,0.00" ) & " Cr",
    ABS ( v ) >= 1e5, FORMAT ( v / 1e5, "₹#,0.0" ) & " L",
    FORMAT ( v, "₹#,0" ) )
```

On a card this reads ₹7.13 Cr. For charts, I prefer dynamic format strings (they keep the value numeric) over `FORMAT`, which returns text and breaks sorting and axes.

### PBI-20. What would you do to make the dashboard trustworthy to an executive?

- Put a "data as of" timestamp and the DQ score (86.2, "fit with caveats") on the first page.
- Give every KPI tooltip the certified definition from the metric catalogue.
- Visually mark provisional periods.
- Show an incident list explaining spikes (sale days, bulk orders, bot spike) so nobody asks why 22 May looks strange.
- Tie numbers exactly to `metrics_daily`, which the Copilot and anomaly system also read, so the same question gets the same answer everywhere.

Trust comes from consistency and visible caveats, not from design polish.

---

## 4. Statistics (15 questions)

### ST-1. What is a sample ratio mismatch, and what did it tell you about EXP-2025-02?

SRM means the observed split between arms differs from the planned split by more than chance allows. EXP-02 (free-shipping threshold ₹299) planned 50/50 and observed 1,808 vs 2,204. A chi-square goodness-of-fit test gives p = 4e-10. That means assignment or logging is broken (in this scenario, a logging bug), so the arms are no longer comparable and **no result from this experiment is valid**. That includes its apparent +28% lift. I reported it as INVALID and recommended fixing the logging and re-running. The singular dbt test `assert_experiment_sample_ratio.sql` catches this before anyone looks at the lift.

### ST-2. EXP-01 was significant. Why not just ship it?

The purchase-rate lift was +9.5% relative, with a 95% CI of +1.0% to +18.8% and p < 0.05, and SRM was fine. But power to detect the pre-registered +5% MDE was only 21%. You need about 10.6k users per arm. With low power, significant results are more likely to overstate the true effect (the winner's curse, or Type M error). The CI's lower bound is near zero. So the decision was "SHIP WITH MONITORING": roll out, keep a 10% holdout, and re-measure. Shipping costs little and a one-page checkout carries little risk, but I would not put +9.5% into a forecast.

### ST-3. What does "inconclusive" mean for EXP-03?

The homepage recommendation widget showed +4.8% with a CI of −6.6% to +17.5%. The data cannot distinguish a meaningful negative effect, no effect, or a meaningful positive one. That is not evidence of no effect. It is an underpowered test. The honest options: run longer or with more traffic until the planned MDE is detectable, or accept that the effect, if any, is smaller than we can afford to measure and decide on cost or strategy grounds. (In the simulation, the true effect is null.)

### ST-4. How do you compute sample size and MDE for a conversion test?

For two proportions with baseline p, relative MDE δ, α = 0.05 two-sided and power 80%:
n per arm ≈ (z₀.₉₇₅ + z₀.₈)² × [p₁(1−p₁) + p₂(1−p₂)] / (p₂ − p₁)², where p₂ = p(1+δ).
Small relative lifts on low base rates need large samples. That is why +5% needed about 10.6k per arm. I compute it before the test (pre-registration) and report achieved power afterwards, labelled as a design check rather than a reinterpretation of the p-value.

### ST-5. Why Welch's t-test instead of Student's t for revenue per user?

Welch does not assume equal variances. Revenue per user usually has a larger variance in the arm that increases purchases. Welch costs almost nothing when variances are equal and protects you when they are not. Because revenue is zero-inflated and heavy-tailed, I pair it with a bootstrap CI and also consider trimming or winsorising extreme B2B-like orders, stated up front and not chosen after seeing results.

### ST-6. Multiple comparisons: what did you correct and how?

The primary metric was pre-registered and uncorrected. Secondary metrics (AOV, revenue per user, CM per user, shipping fee paid) and subgroups (platform, new vs returning) were corrected with **Holm** for family-wise error and **Benjamini–Hochberg** for FDR. Holm is the stricter "is any of these real?" control. BH is appropriate for exploratory screening where some false discoveries are acceptable. With ten subgroups at α = 0.05, the chance of at least one false positive is about 40% without correction. Subgroup findings are hypotheses for a follow-up test, not decisions.

### ST-7. Explain CUPED to a product manager.

"We already know how much each user spent before the test. Much of the variation in test-period spend is just 'big spenders stay big spenders'. CUPED removes that predictable part, so the remaining noise is smaller and we can detect the same effect with fewer users or less time. It cannot create an effect or bias the estimate, because the pre-period happened before anyone was treated."

### ST-8. Why median/MAD instead of mean/standard deviation for anomalies?

The mean and SD are pulled by the outliers you are trying to detect. One Diwali day in the baseline inflates the SD so much that the next real incident looks normal. The median and MAD have a 50% breakdown point, and 1.4826 × MAD estimates σ for normal data, so the z values stay interpretable. I also mask known sale days from the baseline, and I compare against the same weekday because Sunday and Tuesday are different populations.

### ST-9. What is over-dispersion, and how did you correct for it?

For a rate with n trials, the binomial model says the variance is p(1−p)/n. Real daily conversion varies more than that because of traffic mix, campaigns and weather. I estimate φ = median(z²) / 0.455 over a rolling 91-day window, where 0.455 is the median of χ²₁, floor it at 1, and divide z by √φ. This is the quasi-binomial idea. It turns an alert stream that would fire daily into one that fires when something unusual happens.

### ST-10. Why didn't the anomaly detector catch the VoltEdge refund problem?

VoltEdge's refund rate rose gradually. Quarterly, it went from about 3% in early 2025 to 14% in Q3 and 18% in Q4 2025 (simulated), and the defective-line rate from 9% to 16%. Anomaly detectors compare today with the recent baseline, and a slow drift moves the baseline with it. That is a **trend monitoring** problem: brand-level refund rate by order-date quarter with control limits, or a CUSUM, against a fixed reference period (`13_brand_refund_trend.sql`). Knowing which tool fits which failure mode matters more than the tool.

### ST-11. How did you estimate the causal effect of Nova Plus membership?

Four estimators, from least to most credible (all simulated):

| Method | Effect on 90-day orders |
|---|---|
| Naive difference | +439% |
| Regression-adjusted | +392% |
| Coarsened exact matching (ATT) | +215%, with only ~15% of members matched |
| Diff-in-diff on matched strata | +51% |

Members self-select: heavy buyers join because they already buy a lot. Adjusting for observables helps a little. Matching helps more but has poor overlap. DiD removes stable individual differences and gets closest to the simulated truth (+15% order rate while a member), but it is still an upper bound, because the decision to join likely coincides with a rising purchase trend (a violation of parallel trends).

### ST-12. What would it take to prove the membership effect?

Randomisation. Membership cannot be forced, so I proposed a **randomised encouragement design**: offer a free first month to a random 50% of eligible customers. Randomising the offer makes it an instrument. The intent-to-treat effect of the offer is unbiased, and dividing by the difference in uptake gives the complier average causal effect (CACE) via IV. Assumptions: the offer affects orders only through membership (exclusion restriction) and no one joins because they did not get the offer (monotonicity). The first assumption is debatable because a free month is also a discount, and I would say that up front.

### ST-13. What is left-censoring here, and how did you handle it?

Customers who signed up before 2024 had their order history not migrated. Their first order in the data is not their real first order. Including them would put long-tenured customers into 2024 "new" cohorts and inflate early retention and LTV. I flag `is_legacy_customer` and exclude them from cohort, retention, repeat-rate and LTV analyses, while keeping their orders in revenue. The conservative rule treats **all** pre-2024 signups as legacy, even ones who first bought in 2024. That is a known limitation that slightly shrinks 2024 cohorts.

### ST-14. What is right-censoring, and where does it appear?

Outcomes not yet observed because time has not passed: repeat within 90 days for a December customer, 180-day LTV for a September customer, churn for any date after 2025-10-02, refunds on the last ~21 days of orders. The fix is always the same: define a maturity window and compute the metric only on mature units, via the `is_mature_90d/180d/365d` flags, the churn full-window rule and the refund provisional flag. Treating "not yet" as "no" is one of the most common analytical errors in retention and refund reporting.

### ST-15. Explain Simpson's paradox with an example from this data.

A rate can fall overall while rising in every segment, if the mix shifts toward low-rate segments. For conversion: if marketplace-driven or low-intent paid-social traffic grows as a share of sessions, overall conversion can drop even if each channel converts better. The `breakdown` tool splits Δ into a **rate effect** (Σ Δrate × previous share) and a **mix effect** (Σ Δshare × previous rate), plus interaction. This tells leadership whether to fix the funnel or question the traffic. `descriptive.py::mix_vs_rate` does the same for the report.

---

## 5. Business case (15 questions)

### BC-1. Revenue grew 70% in 2025. Why is leadership worried?

Net revenue went from ₹4.19 Cr to ₹7.13 Cr (+70%, simulated), but CM% slipped from 21.7% to 20.4%. The quality of growth changed in Aug–Oct 2025. CM% fell from 23.6% in H1 to 16.5%, because coupon discount rose from 1.5% to 4.9% of gross revenue, and CM after marketing % halved from 19.3% to 9.6%. It recovered to 20.8% in Nov–Dec. Growth that depends on discounting and brings weaker repeat behaviour is not the same as profitable growth. That is the core answer to the executive question.

### BC-2. The Social Blitz campaign had the lowest CAC. Why is it not the best campaign?

CAC measures the cost to acquire, not the value acquired. Social Blitz (Meta, Aug–Oct 2025, 40% first-order discount) had CAC of ₹359 against ₹800–1,200 for other paid campaigns. But its customers produced the lowest 90-day CM per customer (₹212) and a 32% 90-day repeat rate against about 45–55% elsewhere. CM payback was 0.59, meaning the first 90 days of margin covered only 59% of acquisition cost. It acquired 1,979 customers. A deep discount attracts deal-seekers. Judge campaigns on LTV:CAC or payback on mature cohorts, not CAC. (All simulated.)

### BC-3. What would you recommend about Social Blitz?

- Do not scale it in its current form.
- Test a shallower discount, such as 15–20%, or a discount tied to a second order, against a holdout, so the effect is measured, not assumed.
- Move budget toward channels with better mature LTV:CAC. In the simulated run: marketplace 1.93, affiliate 1.75, paid search 1.55, paid social 1.41.
- Track 90-day repeat for the Aug–Oct cohorts to confirm the gap persists.

The simulator puts "stop deep-discount acquisition" at +₹6.3L CM after marketing over 12 months, under stated assumptions (discount −1.5pp, CAC +15%, conversion −1%, refunds −0.5pp).

### BC-4. "Why did revenue decline last month?"

It did not. With data through December 2025, December net revenue was ₹74.0L, +15.7% MoM and +72% YoY (simulated). November fell 33.6% from October's ₹96.3L festive and Blitz peak. The right response corrects the premise first, then answers the likely real question: "the November drop was the festive and campaign comedown, plus a payment issue on the app." The Copilot is built to do exactly this. Analysts who answer the question as asked, when the premise is false, lose credibility.

### BC-5. How would you explain the app payment incident to the CEO in 30 seconds?

"After app release 5.2.0 on 12 November, UPI payments on the app started failing, mostly in Uttar Pradesh, Bihar and West Bengal, where success fell from about 90% to about 50%. National numbers barely moved, so standard monitoring missed it. The segment scan flagged it. We estimate about 64 extra failed orders over three weeks, about ₹1.5 lakh of order value at risk, before the 3 December hotfix. The fix is a release gate on payment success by device, method and state." (Simulated figures.)

### BC-6. What should the release process change after that incident?

- A **staged rollout** (5% → 25% → 100%) with automatic checks on payment success by payment method and app version between stages.
- **Segment-level alerting** in production: device × method × state, not only national.
- A **UPI intent smoke test** on low-end Android devices common in the affected states.
- App version recorded on every payment and session (it already is, as `app_version` on orders), so the scan can attribute failures to a release.

The fix-app-payments scenario is worth +₹5.2L CM after marketing over 12 months in the simulator (+3% conversion assumption).

### BC-7. What would you tell the category head about VoltEdge?

VoltEdge's refund rate rose steadily through 2025, from about 3% per quarter early in the year to 14% in Q3 and 18% in Q4 (simulated), with the defective-line rate going from 9% to 16%. That is a supplier quality problem, not a customer behaviour problem, because the defect share is what rose. Actions: raise it with the supplier with lot and SKU-level evidence, tighten inbound QC, consider pausing promotion of the worst SKUs, and write off defective returns in margin (which the model already does, since defective returns do not recover COGS). Track it with a monthly trend chart and control limits, not the anomaly alerts.

### BC-8. Should NovaCommerce push Nova Plus membership harder?

Not on the basis of the naive number. Members order 439% more in the 90 days after joining (simulated), but most of that is self-selection. The best observational estimate (DiD on matched strata) is +51% and still an upper bound. The simulated truth is modest (+15% order rate while a member). Membership may still be worth promoting, but decide based on an **encouragement experiment** that gives an unbiased estimate, and weigh the free-shipping and discount cost of members against incremental margin, not incremental orders.

### BC-9. Leadership wants a single "north star" metric. What do you propose?

**Contribution margin after marketing**, at date and channel grain. Supported by net revenue (scale), CM% (quality), 90-day repeat rate on mature cohorts (customer quality), and LTV:CAC by channel (acquisition efficiency). Revenue alone rewarded the Social Blitz discounting. CM after marketing would have shown its % halving from 19.3% to 9.6% (simulated). One metric is never enough, but it should be one that cannot be gamed by discounting.

### BC-10. Rank the four simulator scenarios and explain the ranking.

Over 12 months (simulated, assumptions stated):

1. Retention programme (−1pp monthly churn, +10% marketing): +₹6.8L CM after marketing.
2. Stop deep-discount acquisition: +₹6.3L.
3. Fix app payments (+3% conversion): +₹5.2L.
4. Price +3% with −2% conversion: +₹2.7L.

Against a baseline of ₹8.03 Cr net revenue and ₹1.04 Cr CM after marketing, the P10/P90 bands overlap for the top three. So my recommendation considers cost and certainty, not only the point estimate. Fixing app payments is near-certain and cheap, so do it now. Stopping deep discounts is a budget decision. The retention programme needs a test to validate the −1pp assumption.

### BC-11. How would you decide between marketplace and D2C web growth?

Marketplace shows the best mature LTV:CAC in the simulated run (1.93). But marketplace customers are partly the marketplace's customers: commission is taken, first-party data is limited, there are no sessions, and repeat purchases may happen off-platform. D2C web and app carry higher CAC but own the relationship and the data. I would compare CM after commission and marketing per customer over 180 days, consider the strategic value of first-party data, and avoid making marketplace the main growth engine purely on a ratio that ignores dependency risk.

### BC-12. How do you know whether a coupon strategy is working?

Compare incremental margin against a holdout, not redemption counts. A coupon "works" if it creates orders that would not otherwise happen and those orders still carry positive contribution margin after the discount. Look at the discount rate as a % of gross (it moved from 1.5% to 4.9% in Aug–Oct 2025, simulated), CM% of coupon orders against non-coupon orders, and the repeat rate of coupon-acquired cohorts. `17_discount_depth_vs_retention.sql` bins first-order discount depth against 90-day repeat rate. It is correlational, so it motivates a test rather than proving causality.

### BC-13. CFO and CMO report different revenue numbers. What is going on?

Usually both are right, but for different definitions. Finance might report GST-exclusive recognised revenue net of all refunds by refund date. Marketing might report attributed gross order value including cancelled orders. I would lay out the definitions side by side, reconcile them with a bridge (gross placed → cancelled → coupons → returns → GST), and agree on one **certified** name per definition in the metric catalogue. For example, "Net Revenue" is the governed definition, and "Attributed GOV" is a marketing-only metric with a different name. The Copilot refuses "GMV" because it is not certified. That is deliberate.

### BC-14. What leading indicators would you watch weekly?

- Payment success by device × method × state, from the segment scan.
- Checkout conversion.
- Coupon rate as a % of gross.
- New-customer share and paid CAC by campaign.
- 30-day repeat rate of the latest mature cohort, which gives an earlier read than 90 days.
- Brand-level defect refund rate on mature order dates.
- Bot share of sessions (a data-quality leading indicator).

They cover the failure modes that actually happened in 2025: payment breakage, discount-driven margin erosion, supplier quality, and traffic contamination.

### BC-15. If you had one slide for the board, what would it say?

Title: "Growth is strong, but its quality slipped in Q3. Three fixable causes." Revenue +70% YoY. CM% dipped to 16.5% in Aug–Oct on deep-discount acquisition, then recovered to 20.8%. Three risks with owners: discount-led acquisition (weak repeat), app payment failures after 5.2.0 (fixed, needs a release gate), and VoltEdge supplier quality (rising refunds). Ask: approve a shallower-discount test, a staged-release policy, and a membership encouragement experiment. Footer: DQ score 86.2/100, figures simulated.

---

## 6. Project defense (30 hard questions)

These are the questions a senior interviewer uses to find out whether you designed the system or assembled it. Answer with the decision, the alternative you rejected, and the cost you accepted.

### PD-1. Why is `fct_orders` at order grain and not order-line grain? Why not one big table?

Different measures belong to different grains. Shipping fee, gateway fee, coupon at order level and payment status are order facts. Selling price, quantity, COGS and return status are line facts. Putting everything at line grain forces you to allocate order-level amounts to lines, or repeat them and risk double counting. So I kept both: `fct_order_items` (coupons allocated pro-rata for product-level net revenue) and `fct_orders`, and I test that they reconcile (`assert_no_fanout_order_items`). One big table is convenient for a single dashboard, but it breaks as soon as someone sums a repeated column. The star schema makes the grain explicit and each measure additive at its own grain. For BI convenience I pre-aggregate into `metrics_daily`, a wide table at a clean daily grain.

### PD-2. Why PostgreSQL and not Snowflake, BigQuery or DuckDB?

The data is about 60k orders and a few million events, which is laptop scale. Postgres 16 in Docker is free, reproducible with `make db-up`, runs as a CI service container, supports everything I needed (window functions, `FILTER`, `percentile_cont`, partial and BRIN indexes, `COPY`), and is what many Indian startups run as their first analytics database. DuckDB would be faster for pure analytics but is less representative of a shared multi-user warehouse and of Power BI connectivity. The SQL is dbt-managed and mostly ANSI, so moving to Snowflake or BigQuery means changing the adapter and a few functions (regex casts, `at time zone`). I documented that path rather than paying for it.

### PD-3. Why dbt? Couldn't you do this in stored procedures or Python?

dbt gives four things I would otherwise build by hand: a dependency graph (`ref()`), so models build in the right order; tests next to models (about 180); documentation and lineage; and environment-aware builds, so CI can build a 1,500-customer sample with the same code. Stored procedures hide logic in the database, are hard to review and have no native testing. Pandas transformations would duplicate logic that BI and the Copilot also need in SQL. dbt makes transformations version-controlled, reviewable SQL, which is what analytics engineering means in practice.

### PD-4. Where do you draw the line between SQL and pandas?

If the output is a table other people or tools will read, or the logic defines a metric, it goes in SQL/dbt: set-based, testable and shared by Power BI, the anomaly detector and the Copilot. If the task is inference, simulation or iteration (tests, bootstraps, matching, STL, ETS, Monte Carlo), it goes in Python, reading governed tables. The anti-pattern I avoided is pulling raw rows into pandas and re-implementing "completed and reportable" filters there. That is how two versions of revenue appear.

### PD-5. How would this design change at 1 billion rows?

Documented in `sql/performance/README.md`:

1. Make the large facts dbt **incremental** with a `unique_key` and a 14-day lookback, so late refunds and status changes are reprocessed.
2. Partition by date. In Postgres use monthly range partitions and BRIN on the time column. In BigQuery or Snowflake use partitioning or clustering on `order_date` and `customer_id`.
3. BI reads only aggregates (`metrics_*`, `mart_*`), with Import plus incremental refresh or aggregation tables.
4. Store per-customer sequences (`customer_order_number`) incrementally instead of windowing the full fact.
5. Move sessionisation of billions of events upstream (streaming or Spark), with dbt owning business logic on the result.

At that scale I would also move off a single Postgres to a columnar warehouse. The model design (grains, governed columns, tests) stays the same, and that is the part that matters.

### PD-6. What was your slowest query, and how did you find the fix?

A model build took 36 s. `EXPLAIN (ANALYZE, BUFFERS)` showed a correlated `EXISTS` against a view executing as a SubPlan once per order. The view applied regex casts, so no index was usable and the subquery re-evaluated the view each time. I rewrote it as a pre-aggregated set-based join (hash join, one pass): the query went from 24.8 s to 0.18 s and the model from 36 s to 1 s on the 15k-customer development dataset. I also materialised the big staging views as indexed tables. The lesson I would state: measure first, and look for row-by-row patterns hidden inside set-based SQL.

### PD-7. How do you know your retention numbers are correct?

Several independent checks:

- **Invariant test:** `assert_retention_month0_is_100pct.sql`. Every cohort must be 100% active in month 0, so any join or date bug breaks it.
- **Independent recomputation:** `05_cohort_retention_from_scratch.sql` computes retention directly from `fct_orders`, separately from `fct_customer_monthly`/`mart_cohort_retention`, and they must match.
- **Monotonic sanity:** cumulative "ever returned" must not decrease, and cohort sizes must equal first-time buyers per month.
- **Censoring rules:** legacy customers excluded, and immature cells not shown.
- **Ground truth:** the generator's planted drop in repeat rate for Aug–Oct 2025 cohorts was recovered: 42–44% against 55–57% for Jun–Jul (simulated).

### PD-8. How would you detect metric drift, meaning a metric changing because of the pipeline and not the business?

Three layers:

1. `assert_no_unexpected_metric_shift.sql` compares key metrics for historical closed periods between builds. Last year's revenue should not change unless late refunds explain it.
2. The raw-layer scan and `assert_raw_duplicate_rate_by_day` catch upstream volume changes.
3. Definitions live in one place (the metric catalogue seed and dbt models), and every change goes through code review with a changelog.

A metric changing historically without a documented reason is a data incident, even if the new number is "better".

### PD-9. Why should leadership trust the dashboard?

Because trust is engineered, not asserted:

- One definition per metric (certified catalogue), computed once in dbt and read by every consumer.
- About 180 tests run on every build (173 pass, 8 warn, 0 errors in the full run). The warnings are the planted defects, each documented and mitigated.
- A DQ scorecard (86.2/100, "fit with caveats") shown on the dashboard, not hidden.
- Reconciliation from raw to governed (`22_layered_reconciliation.sql`) that shows why raw and governed numbers differ, for example 2025-03-18.
- Provisional periods and incidents explained visually.

I would also say what it does *not* guarantee: attribution is last-touch, and LTV is a 180-day proxy.

### PD-10. A source system adds, renames or drops a column tomorrow. What happens?

- **Added column:** ingestion detects drift, runs `ALTER TABLE ADD COLUMN ... text`, logs it in `raw._ingestion_audit`, and loads the file. Nothing downstream breaks, and someone reviews whether to model it.
- **Dropped or renamed required column:** the contract in `contracts.yml` rejects the file. It is logged as `rejected`, and the freshness test (`assert_orders_fresh.sql`) then fails, so the problem is loud rather than silently loading NULLs.
- **Type change** (a number arriving as "12,500" or "N/A"): raw accepts it as TEXT. `safe_numeric` returns NULL, and `max_null_rate` fails the build.

The principle: additive changes are tolerated, breaking changes fail loudly and early.

### PD-11. Finance and Marketing define revenue differently. How do you resolve it?

I do not pick a winner. I make the difference explicit. Steps:

1. Write both definitions precisely (grain, inclusions, timing, tax).
2. Build a bridge that reconciles them with named steps.
3. Get the metric owner, usually Finance for revenue, to certify one as "Net Revenue".
4. Give the other a different certified name ("Attributed GOV") instead of letting two metrics share one name.

In this project the catalogue fixes Net Revenue = gross − coupons − processed **return** refunds. Cancellation refunds are excluded because cancelled orders never enter gross. That rule is precisely the kind of thing two teams disagree about. The goal is one name, one number and documented alternatives.

### PD-12. Members order 4× more. Isn't that proof membership works?

No. That is correlation driven by selection. Customers who already buy often are the ones who join. The naive +439% shrinks to +392% with regression adjustment, +215% with matching (with only about 15% of members having comparable non-members) and +51% with DiD on matched strata, against a simulated truth of +15%. Each method removes a different source of bias, and none removes selection on unobserved intent. The honest summary is "positive, much smaller than it looks, magnitude unknown". That is why I recommended an experiment.

### PD-13. How would you actually prove causality here?

A randomised encouragement design: a free first month for a random 50% of eligible customers. Randomisation balances observed and unobserved factors. The ITT of the offer is unbiased, and IV gives the CACE for compliers. I would pre-register the outcome (90-day contribution margin, not orders, because members get free shipping), the sample size, and a guardrail on margin. Where randomisation is impossible, the next-best options are a geo holdout, a regression discontinuity if there is an eligibility threshold, or DiD with an explicit parallel-trends check on pre-periods. I would present any of them as weaker evidence.

### PD-14. An executive disagrees with your analysis. What do you do?

First, find out what they believe and why, because they often have context I do not have (a pricing change, a partner deal). Then separate the disagreement into data (are we looking at the same number and definition?), method (is the attribution or causal approach appropriate?) and interpretation (what should we do?). For data, I show the reconciliation. For method, I show sensitivity: does the conclusion survive a different attribution rule or window? For interpretation, the decision is theirs, and my job is to make the trade-off and its uncertainty clear. For example: "Social Blitz lowered CAC to ₹359 but its customers repeat at 32%. If you value volume for a fundraise, that may be a valid choice, but it costs margin." I do not escalate, and I do not quietly cave. I put the disagreement and the evidence in writing.

### PD-15. You have two weeks, not two months. What do you cut?

I keep the core that answers the executive question: ingestion with dedupe, staging with casting, `fct_orders`/`fct_order_items`/`fct_marketing_spend`, the metric definitions, about 30 essential tests (uniqueness, not-null, no fan-out, reconciliation), channel economics, cohort retention and a 3-page dashboard. I cut the Copilot, the decision simulator, the causal membership analysis, STL cross-checks, SCD2 (use current attributes and document the limitation), the forecast, and most of the anomaly classification. Experiments stay only if a live decision depends on them. Correct governed numbers come first. Everything else is a multiplier on trust you have not yet earned.

### PD-16. What assumptions would make your LTV wrong?

LTV here is 180-day cumulative contribution margin per acquired customer, mature cohorts only. It is wrong if:

- **The horizon is too short.** Membership or subscription value accrues beyond 180 days, so LTV:CAC understates channels with loyal customers.
- **Future cohorts differ from mature ones.** The newest (Aug–Oct) cohorts are the least mature and the most different.
- **Attribution is wrong.** Last non-direct touch credits the closer and under-credits upper-funnel channels.
- **Costs are missing.** Customer support cost, fixed fulfilment, and returns handling beyond COGS recovery are not in CM.
- **Imputed costs are wrong.** About 2% of products use category-median cost ratios.
- **Legacy exclusion shrinks 2024 cohorts,** which is conservative.

LTV:CAC ratios like 1.93 against 1.41 (simulated) are for ranking channels, not for valuing the company.

### PD-17. How would you productionise this?

- **Orchestration:** Airflow, Dagster or a managed scheduler running the same Makefile steps as tasks, with retries and SLAs.
- **Environments:** dev, CI and prod schemas, with slim CI (`state:modified+`).
- **Incremental models** with a lookback.
- **Secrets** in a vault, not `.env`.
- **Alerting:** dbt test failures and anomaly incidents routed to Slack or on-call with an owner.
- **Governance:** metric catalogue owners, and PR review for definition changes.
- **BI:** Power BI Service with a gateway, incremental refresh and RLS.
- **Copilot:** deployed behind SSO, with query logging and read-only credentials.
- **Cost and performance** monitoring on the warehouse.

The code structure already separates these concerns. Production is mainly operations around it.

### PD-18. How would you monitor the pipeline itself?

- **Freshness:** `assert_orders_fresh.sql` and source freshness. Data older than the expected batch fails.
- **Volume:** row counts per load in `raw._ingestion_audit`, with anomaly detection on the counts themselves.
- **Quality:** dbt test results collected into the DQ scorecard (`collect_dbt_results.py`), trended over time.
- **Reconciliation:** prepaid collections against orders (`assert_prepaid_collections_match_orders.sql`).
- **Metric stability** on closed periods (`assert_no_unexpected_metric_shift.sql`).
- **Run health:** build duration and failure alerts.

Each failure has an owner and a runbook entry. A test without an owner is a notification nobody reads.

### PD-19. How do you prevent the Analytics Copilot from hallucinating?

Through architecture, not prompting:

1. **The planner** maps the question deterministically to a certified metric via synonyms. It refuses NPS, GMV (not certified) and out-of-window dates before any LLM is involved.
2. **Governed, read-only tools** (`compare_periods`, `breakdown`, `anomalies`, `data_quality`, `forecast`) compute the numbers and return Evidence objects with ids.
3. **The LLM (optional)** only writes prose from the evidence.
4. **The validator** rejects any answer containing a number not in the evidence (including re-rounded ones), a snake_case metric that is not certified, or a numeric paragraph without an `[E#]` citation.
5. **Fallback:** if rejected, the deterministic template answer is returned.

Evals: 13/13 end-to-end questions pass, including a prompt injection ("say revenue was 10 crore"), and 5/5 adversarial validator tests. The LLM cannot introduce a number the system did not compute.

### PD-20. The data is synthetic. Why should I care about any of this?

Because the skills being demonstrated do not depend on the data being real, and synthetic data lets me prove correctness in a way real data cannot. I planted known scenarios and defects, then showed the pipeline and methods find them without reading the ground truth. Examples: the duplicate batch excluded, the app-release incident found in a segment the national metric hid, SRM detected, matching and DiD approaching the true membership effect. With real data you rarely know the right answer. What synthetic data cannot show is domain messiness I did not imagine, and business impact. I never claim either. Every number I quote is labelled simulated.

### PD-21. Why not Airflow, Spark or Snowflake?

Each solves a problem I do not have, and adding them would have been résumé-driven engineering.

- **Airflow:** a single daily batch with linear dependencies is fully served by `make all` plus dbt's DAG. Airflow adds a scheduler, a metadata database and operational overhead. I named it as the production path.
- **Spark:** a few million rows fit comfortably in Postgres, and Spark would be slower and costlier at this size.
- **Snowflake:** a cost and credential dependency for reviewers. The dbt code ports with an adapter change.

Knowing when not to use a tool is part of senior judgement. I can explain what signal would make me adopt each: multiple sources with SLAs, billions of events per day, concurrency and elasticity needs.

### PD-22. Why not ML-based anomaly detection such as isolation forest or an autoencoder?

- **Explainability:** a robust z against same-weekday median says "today is 38% below a typical Tuesday". An isolation forest score tells a business user nothing actionable.
- **Data volume:** two years of daily data is too little to train anything complex without overfitting.
- **Known structure:** weekly seasonality, festivals and binomial rates are known structure. Encoding it directly beats learning it.
- **What actually matters:** the hard part was not detection. It was masking sale days, over-dispersion, segment scanning and classifying incidents into expected, data-quality, outlier and signal. The S2 incident was invisible nationally, and no top-line model, ML or not, would have found it.

I would consider ML for high-dimensional segment scanning at larger scale.

### PD-23. Walk me through your SCD2 decisions.

- **What is tracked:** customer city/geo (from CDC rows) and product price/cost. Those are the attributes where "as of order time" changes the answer (regional revenue, historical margin). Other attributes are type 1 (overwrite).
- **Intervals:** half-open `[valid_from, valid_to)` with a far-future `valid_to` for current rows, so joins are simple and never double-match.
- **First version valid from 1900-01-01,** so orders before the first captured change still join. The alternative, starting at the first CDC timestamp, orphans early orders.
- **Deduplicate exact duplicate CDC rows and collapse no-op changes** to avoid zero-length versions.
- **An Unknown member** for guests and orphans.
- **Tests:** no overlap, no fan-out.

The known trade-off: 1900-01-01 assumes the first known city was always the city, which is an assumption and not a fact.

### PD-24. How biased is your attribution, and in which direction?

Last non-direct touch: session UTM takes priority over the signup campaign for first orders. It is biased toward **closing channels** (paid search, affiliate coupons, marketplace) and against **awareness channels** (paid social). Paid social's 1.41 LTV:CAC (simulated) is therefore probably understated relative to paid search's 1.55. It also cannot see cross-device journeys, because there is no cross-device visitor id, so a person who clicks a Meta ad on mobile and buys on desktop web is credited elsewhere. Better options are geo-holdout or conversion-lift tests for incrementality and, longer term, a media mix model. I present channel ratios as directional and recommend lift tests before large budget shifts.

### PD-25. Legacy customers: why exclude them, and what does the exclusion cost?

Their pre-2024 history was not migrated, so their first order in our data is not their first order (left-censoring). Including them would label loyal old customers as "new in January 2024" and inflate 2024 retention and LTV. I flag `is_legacy_customer` and exclude them from cohort, repeat, churn-cohort and LTV analyses, while keeping all their orders in revenue metrics. The cost: the rule treats **all** pre-2024 signups as legacy, including ones who signed up earlier but first purchased in 2024. That slightly under-counts true 2024 new customers. It is conservative and documented. A better rule would need signup-to-first-order data from the legacy system.

### PD-26. How do you handle late-arriving data?

Three kinds:

- **Late facts, such as refunds.** A second refund batch arrived on 2026-01-12. The refund rate is measured by order date, and the last ~21 days are flagged provisional (`is_refund_mature`). At scale, incremental models reprocess a lookback window.
- **Late dimensions** (orphan customers or products that arrive after their orders). The facts map to an Unknown member with `is_orphan_customer` or `is_orphan_product` flags, and the next build re-links them automatically, because marts are rebuilt from raw.
- **Late corrections** (status changes). The accumulating snapshot updates in place.

The metadata columns (`_loaded_at`, `_batch_id`) let me answer "what did we know on date X?", which matters when a number changes after it was reported.

### PD-27. How did you handle PII?

- **Minimise:** marts expose only `email_hash`, not raw email. Names and phone numbers are not carried into marts.
- **Test orders:** `@novacommerce.test` emails are used only to flag internal test orders in staging, then dropped.
- **Access:** raw would be restricted to engineering, marts to analysts, and RLS in Power BI.
- **The Copilot** only sees aggregated evidence, never row-level customer data, so no PII can reach an LLM.

For India specifically, the Digital Personal Data Protection Act 2023 makes purpose limitation and minimisation legal requirements, not just good practice. A hashed email without a salt is pseudonymous, not anonymous. In production I would use a keyed hash and treat it as personal data.

### PD-28. What is the cost of being wrong in this analysis?

It is asymmetric, and I would design around that:

- **Blitz conclusion wrong:** if we cut Social Blitz and its customers would have matured well, we lose some volume. If we scale it wrongly, we lose margin at scale. I would test a shallower discount instead of making a binary call.
- **EXP-01 wrong:** shipping a one-page checkout with a true effect near zero costs little, which is why "ship with monitoring" is acceptable at low power.
- **Membership wrong:** believing the naive +439% could justify heavy spending on free shipping for customers who would have bought anyway. That is the costliest error here, so it gets the strongest evidence requirement (an experiment).
- **Missing an S2-type incident:** that costs revenue every day, which justifies tolerating 3 false-positive business signals.

### PD-29. What would you do differently?

- **Model the metrics layer in a semantic layer** (dbt MetricFlow or similar) instead of a seed catalogue plus hand-built metrics models. It would give the Copilot and Power BI one compiled definition.
- **A better legacy rule** using first-order dates from a migrated summary table.
- **A cross-device identity stitch,** or at least a logged-in user id on sessions, so Revenue per Visitor is not a session proxy.
- **A festival regressor in the forecast** to reduce the −13% bias.
- **Incremental models from the start,** even at small scale, to exercise lookback logic.
- **Contract tests owned by source teams,** not only by me.
- **A simpler first dashboard page.** Six pages is a lot, and an executive needs one.

### PD-30. How do you know your synthetic scenarios are not circular, that you did not just find what you planted?

A fair challenge. Three safeguards:

1. **Separation:** the analysis, anomaly and causal code never reads the ground-truth scenario tables. They are used only in evaluation, such as `evaluate()` in `anomaly/run.py`.
2. **Methods chosen for general failure modes,** not tuned to a scenario. The segment scan checks every dimension, not specifically app × UPI × UP. The SRM test runs on every experiment.
3. **Results that are not flattering.** The causal methods do **not** recover the true +15%. The best is +51%, which I report as an upper bound. EXP-01 is underpowered. The anomaly system has 3 unexplained business signals, and the forecast has −13% bias.

If I had tuned everything to the plants, every number would look perfect. The imperfect results are evidence that I did not.

### PD-31 (bonus). Isn't about 180 dbt tests overkill? Doesn't it slow development?

The count is not the point. Coverage of failure modes is. Most tests are cheap generic ones (unique, not_null, relationships, accepted_values). The expensive, high-value ones are the singular tests that encode business invariants: no fan-out, SCD2 no overlap, month-0 retention = 100%, payment reconciliation, SRM, metric shift on closed periods. The 8 warnings in the full run are the planted defects. Each is known and mitigated, and each is configured to warn rather than error so that it stays visible without blocking. CI runs the full build of 181 nodes on the 1,500-customer sample on every push. The alternative is finding the problem in a board deck.

---

## 7. Red-flag answers to avoid

- **"The project increased revenue by X%."** It is synthetic. Say "on a simulated dataset, the analysis identified…". Claiming real impact from a portfolio project ends interviews.
- **"I used an LLM so the Copilot understands the data."** The LLM is optional and untrusted. The value is the planner, governed tools and validator. Lead with those.
- **"The p-value was below 0.05 so we shipped."** Mention SRM, power, the CI, and the decision rule. For EXP-01 the answer is "ship with monitoring" precisely because power was 21%.
- **"Membership causes 4× more orders."** That is selection bias. Walk down the estimator ladder and recommend an experiment.
- **"Average of daily conversion rates" or "average of cohort retention percentages."** Always sum the numerator, sum the denominator, then divide.
- **"I deleted the bad rows."** Bots, invalid dates and test orders were flagged and excluded from governed metrics, not deleted. Deletion destroys auditability.
- **"Negative values are errors."** Marketing credit notes are legitimate negatives. Know why before you fix.
- **"I used Airflow, Spark and Snowflake because they're industry standard."** I did not, and that was deliberate. Explain when each would become necessary.
- **"Refund rate is falling in December, great news."** The last ~21 days are provisional because refunds arrive late.
- **"Churn went up in Q4 2025."** Churn needs a full 90-day forward window. Q4 churn is not measurable yet with data ending 2025-12-31.
- **"LTV:CAC of 1.93 means marketplace is the best channel."** It is last-touch, 180-day, mature cohorts only, and ignores marketplace dependency and commission risk.
- **"The anomaly detector catches everything."** It missed nothing it was designed for, but slow drifts like VoltEdge need trend monitoring, and the national S2 signal was below threshold.
- **"Data quality is 100%."** It was 86.2/100, fit with caveats. Knowing your caveats is the senior answer.
- **Unfamiliarity with your own files.** If you cannot say where the month-0 retention test lives or what `is_countable` means, the interviewer will assume someone else built it.
- **Blaming the data.** "The data was messy" is not an answer. "Here is each defect type, how it was detected, and how it was handled" is.
