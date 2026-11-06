# START HERE: complete guide to the NovaCommerce project

This is the one document to read first. It explains:

1. [What the project is, in one picture](#1-the-big-picture)
2. [What to install](#2-what-to-install-step-0)
3. [How to run it, step by step, from Step 1 to the end](#3-run-the-project-step-by-step)
4. [What every folder and file does](#4-folder-by-folder-guide)
5. [How one order travels through the whole system](#5-follow-one-order-through-the-system)
6. [How to build the Power BI dashboard](#6-build-the-power-bi-dashboard)
7. [How to put it on GitHub and LinkedIn](#7-publish-github-and-linkedin)
8. [In what order to study it for interviews](#8-learning-path-how-to-study-this-for-interviews)
9. [Troubleshooting](#9-troubleshooting)
10. [Command cheat-sheet](#10-command-cheat-sheet)

---

## 1. The big picture

**The business question:** *"Why is NovaCommerce's profitable growth changing, what is driving it, what risks are emerging, and what should leadership do?"*

**The idea:** we create a realistic, messy dataset for a fictional Indian e-commerce company, clean and model it the way a real analytics team would, define every metric once, analyse it, and present decisions.

```
STEP 1          STEP 2            STEP 3                         STEP 4              STEP 5                STEP 6
Generate   →    Ingest       →    Transform (dbt)            →   Analyse (Python) →  Present          →    Explain
fake source     load CSVs into    raw → staging →                stats, experiments,  6-page dashboard,     README, memo,
data (CSV)      PostgreSQL        intermediate → marts →         anomalies, DQ,       Power BI,             interview prep
                "raw" schema      metrics  (+125 tests)          simulator, copilot   Copilot
python/nova/    ingestion/        dbt/nova_dbt/                  python/nova/*        powerbi/              docs/, reports/
generator/
```

Everything is **one command** (`make all`) once your computer is set up. Each step writes its results into a **schema** (a named area) of the PostgreSQL database:

| Schema | Written by | Contains |
|---|---|---|
| `raw` | ingestion | the CSVs exactly as received (all TEXT) + load audit |
| `seeds` | dbt seed | small mapping tables (channel names, categories, metric catalogue) |
| `staging` | dbt | cleaned, typed, de-duplicated copies of each source |
| `intermediate` | dbt | business logic (order status, SCD2, attribution) |
| `marts` | dbt | the star schema (facts + dimensions) and analytic marts |
| `metrics` | dbt | governed metrics: `metrics_daily`, `metrics_monthly`, `metrics_daily_by_dimension`, `metric_catalog` |
| `dq`, `dq_failures` | dbt + Python | test results, data-quality scorecard, rows that failed tests |
| `analytics` | Python | anomalies, experiment results, segments, forecast, simulator outputs |

---

## 2. What to install (Step 0)

| Tool | Why | Get it |
|---|---|---|
| **Git** | version control, GitHub | git-scm.com |
| **Python 3.10+** (3.11 recommended) | generator, ingestion, analytics | python.org (Windows: tick *"Add Python to PATH"*) |
| **Docker Desktop** | runs PostgreSQL 16 with one command | docker.com |
| **VS Code** (recommended) | editor, with the *Python*, *dbt Power User* and *SQLTools* extensions | code.visualstudio.com |
| **Power BI Desktop** (Windows only, free) | build the `.pbix` | Microsoft Store |
| **make** (Mac/Linux have it. On Windows it's optional) | shortcut commands | Windows: use the PowerShell commands in section 3 instead |

> **Mac users:** Power BI Desktop does not run on macOS. Run the pipeline on the Mac, then copy `powerbi/data/` (the CSV pack) to a Windows PC or VM and build the report there. Alternatively, use the ready HTML dashboard (`powerbi/dashboard/NovaCommerce_Dashboard.html`), which works in any browser.

Check the installs in a terminal:

```bash
git --version      # any
python --version   # 3.10 or newer   (Mac/Linux may need `python3`)
docker --version   # any; Docker Desktop must be RUNNING
```

---

## 3. Run the project, step by step

Run every command from the **project root folder** (`nova-commerce-analytics/`). Each step says what you should see, so you know it worked.

### Step 1: Get the code and create a Python environment

```bash
cd nova-commerce-analytics
python -m venv .venv
# Mac/Linux:
source .venv/bin/activate
# Windows PowerShell:
.venv\Scripts\Activate.ps1
pip install -e ".[dev,copilot]"
cp .env.example .env          # Windows: copy .env.example .env
```

✅ The prompt shows `(.venv)`, and `pip` ends with "Successfully installed … dbt-core … pandas …".
**What happened:** `pyproject.toml` lists every dependency. `.env` holds the database credentials (never commit it).

### Step 2: Start the database

```bash
make db-up
# Windows (no make): docker compose -f docker/docker-compose.yml up -d --wait
```

✅ `docker ps` shows a container `nova_pg` with status *healthy*.
**What happened:** `docker/docker-compose.yml` started PostgreSQL 16 on `localhost:5432` (user/password/db = `nova`).

### Step 3: Generate the source data

```bash
make generate
# Windows: $env:PYTHONPATH="python"; python -m nova.generator.run --customers 30000 --out data/landing
```

✅ It prints *"simulated ~59,000 orders"*, then row counts, in about 15 seconds. The folder `data/landing/2026-01-01/` now has 16 CSV files, and `data/landing/2026-01-12/refunds.csv` holds the late-arriving refunds.
**What happened:** `python/nova/generator/` simulated two years of customers, orders, payments, refunds, sessions, campaigns, tickets and experiments. It also **deliberately injected** six business stories (`scenarios.py`) and about 20 data defects (`defects.py`). `data/ground_truth/` records what was planted, so the methods can be checked later. Analysis code never reads it.

### Step 4: Load the data into PostgreSQL

```bash
make ingest
# Windows: python ingestion/load_raw.py --landing data/landing
```

✅ 17 lines of `load <table> … rows`, then `summary: {'loaded': 17}`. **Run it a second time:** every file says *"already loaded"*. That is idempotency working.
**What happened:** `ingestion/load_raw.py` checked each file against `ingestion/schemas/contracts.yml`, stored it as TEXT in `raw.<table>`, and logged it in `raw._ingestion_audit` (file hash, rows, status).

### Step 5: Transform and test with dbt

```bash
make dbt-build
# Windows:
#   cd dbt/nova_dbt
#   dbt deps --profiles-dir .
#   dbt build --profiles-dir .
#   cd ../..
#   python -m nova.dq.collect_dbt_results
```

✅ The last line reads `Done. PASS=173 WARN=8 ERROR=0 … TOTAL=181` (about 30 seconds).
**What happened:** dbt loaded the seeds, built 50 models (staging → intermediate → marts → metrics) and ran 125 tests. The **8 WARNs are expected**: they are the planted source defects (orphan products, invalid dates, the duplicate batch, the SRM experiment, and so on). **ERROR must be 0.** Results are saved into `dq.dbt_test_results`.

Look at the result yourself:

```bash
docker exec -it nova_pg psql -U nova -d nova -c "select month, net_revenue, cm_pct from metrics.metrics_monthly order by month desc limit 3;"
```

### Step 6: Data-quality scorecard

```bash
make dq          # python -m nova.dq.scorecard
```

✅ It prints dimension scores and `OVERALL 86.2`, and writes `reports/data_quality_scorecard.md`.

### Step 7: Statistics, experiments, causal analysis, segments, forecast

```bash
make analytics   # python -m nova.analytics.run_all
```

✅ It writes 5 reports in `reports/`: `statistical_analysis.md`, `experiment_readouts.md`, `causal_membership.md`, `customer_segmentation.md`, `revenue_forecast.md`.

### Step 8: Anomaly detection

```bash
make anomalies   # python -m nova.anomaly.run
```

✅ It writes `reports/anomaly_detection.md`, and the console lists 2 segment incidents, including **payment_success_rate · device_type = mobile_app** (the planted app bug).

### Step 9: Decision simulator

```bash
make simulate    # python -m nova.simulator.engine --example
```

✅ A table of 5 scenarios, plus `reports/decision_simulator.md`.

### Step 10: Analytics Copilot (AI)

```bash
make copilot-eval                          # python -m nova.copilot.evals   -> 13/13 and 5/5
python -m nova.copilot.assistant "Why did revenue drop in November 2025?"
make copilot-app                           # optional Streamlit UI in the browser
```

It works **without any API key** (`COPILOT_PROVIDER=offline` produces deterministic template answers). To use a real LLM, set `COPILOT_PROVIDER=anthropic` and `ANTHROPIC_API_KEY` (or `ollama`) in `.env`. The validator still checks every number.

### Step 11: Docs, dashboard and Power BI data pack

```bash
make docs        # regenerates docs/04_data_dictionary.md and the README charts
make dashboard   # builds powerbi/dashboard/NovaCommerce_Dashboard.html + powerbi/data/*.csv
```

✅ Open `powerbi/dashboard/NovaCommerce_Dashboard.html` in Chrome or Edge. You get the full 6-page interactive dashboard.

### Step 12: Tests and lint (what CI runs)

```bash
make test        # pytest -> 17 passed
make lint        # ruff   -> All checks passed
```

### The shortcut

Steps 3–11 in one go (about a minute on a laptop):

```bash
make all
```

### Step 13: Build Power BI, publish, prepare for interviews

See sections 6, 7 and 8 below.

---

## 4. Folder-by-folder guide

```
nova-commerce-analytics/
├── START_HERE.md          ← this guide
├── README.md              ← the case study recruiters read (results, charts, how to run)
├── Makefile               ← all commands (make help lists them)
├── pyproject.toml         ← Python dependencies + ruff/pytest settings
├── .env.example           ← template for database / LLM settings (copy to .env)
├── .gitignore             ← keeps generated data, secrets and build output out of Git
├── LICENSE                ← MIT
├── .github/workflows/     ← CI pipeline
├── docker/                ← PostgreSQL container
├── data/                  ← generated CSVs (ignored by Git) + ground truth
├── ingestion/             ← CSV → PostgreSQL loader
├── dbt/nova_dbt/          ← all SQL transformations and tests
├── python/nova/           ← all Python: generator, analytics, anomaly, dq, simulator, copilot, dashboard
├── sql/                   ← interview-grade analysis queries + performance studies
├── reports/               ← generated results (committed so reviewers can read them)
├── powerbi/               ← dashboard, CSV data pack, DAX, spec, theme, screenshots
├── docs/                  ← strategy, requirements, architecture, metrics, memo, interview prep
├── notebooks/             ← your own exploration (rules in README)
└── tests/                 ← Python unit tests
```

### `.github/workflows/ci.yml`

On every push, GitHub starts a PostgreSQL container, generates a small 1,500-customer sample, loads it, runs `dbt build` with all tests, and runs `pytest` and `ruff`. A red ❌ on GitHub means something broke.

### `docker/`

| File | Purpose |
|---|---|
| `docker-compose.yml` | Starts PostgreSQL 16 (`nova_pg`) on port 5432 with tuned memory settings. The optional pgAdmin UI starts with `docker compose --profile tools up` (http://localhost:5050) |

### `data/`

| Path | Purpose | In Git? |
|---|---|---|
| `landing/<batch_date>/*.csv` | Generated source extracts. `2026-01-01` is the main batch; `2026-01-12` holds late refunds | no (regenerate with `make generate`) |
| `sample/landing/` | small dataset for CI (`make sample`) | no |
| `ground_truth/scenarios.json` | the six planted business stories (S1–S6) with dates and sizes | yes |
| `ground_truth/defects.json` | every injected defect and how many rows it affected | yes |
| `ground_truth/row_counts.json` | rows per table | yes |
| `README.md` | explains the above | yes |

### `python/nova/generator/`: Step 1, create the data

| File | What it does |
|---|---|
| `config.py` | Settings: seed (42), date range 2024–2025, number of customers, extraction dates |
| `scenarios.py` | **The ground truth.** S1 discount blitz, S2 app UPI bug, S3 VoltEdge refunds, S4 duplicate batch, S5 experiments (one with an SRM bug), S6 membership self-selection, the legacy customers, the bot spike |
| `calendar.py` | Demand curve: growth trend × weekday pattern × Indian festive calendar (Diwali, Big Festive Sale, …) |
| `reference.py` | Cities/states/tiers, product catalogue (6 categories, brands, prices, costs), campaigns, channel behaviour (order rate, churn, CAC) |
| `commerce.py` | The simulation engine. Each customer signs up, orders as a Poisson process, may join Nova Plus, churns, pays (with failures), gets deliveries, returns items, raises tickets, and is enrolled in experiments |
| `web.py` | Web/app traffic: non-converting sessions, funnel events, browsers, app versions, the bot spike |
| `defects.py` | Injects about 20 real-world data problems (duplicates, messy labels, nulls, invalid dates, paise, negative refunds, orphans, …) and logs them |
| `run.py` | Entry point: runs all of the above and writes the CSV batches + ground truth |

### `ingestion/`: Step 2, load

| File | What it does |
|---|---|
| `load_raw.py` | Loads each CSV into `raw.<table>` as TEXT using `COPY`. Adds `_batch_id`, `_source_file`, `_loaded_at`. Skips files already loaded (SHA-256 hash). Rejects files missing required columns. Adds new columns automatically (schema drift). Logs everything in `raw._ingestion_audit` |
| `schemas/contracts.yml` | Data contracts: the required columns and natural key for each source table |

### `dbt/nova_dbt/`: Step 3, transform and test

| Path | What it does |
|---|---|
| `dbt_project.yml` | Project config: layer → schema/materialisation, variables (data window, bulk threshold, churn window) |
| `profiles.yml` | Database connection (reads `PG*` environment variables). Targets `dev` and `ci` |
| `packages.yml` / `package-lock.yml` | Uses `dbt_utils` (installed by `dbt deps` into `dbt_packages/`, ignored by Git) |
| `seeds/*.csv` | Small reference tables: `channel_mapping` (FB/Meta → paid_social …), `category_mapping`, `payment_method_mapping`, `ticket_category_mapping`, `dim_channel_seed`, and **`metric_catalog_seed` (the certified metric list)** |
| `macros/casting.sql` | `to_ist()` (UTC → IST), `safe_numeric()`, `safe_date()`, `norm()`, `dedupe()` |
| `macros/tests.sql` | Custom tests: `not_negative`, `within_data_window`, `not_before`, `max_null_rate`, `sum_reconciles` |
| `macros/generate_schema_name.sql` | Makes models land in `staging`, `marts`, … (not `public_staging`) |
| `models/staging/` | One `stg_*` per source: cast, rename, de-duplicate, standardise labels, flag bots. `_sources.yml` declares the raw tables and freshness; `_staging.yml` holds the tests |
| `models/intermediate/` | `int_customers__scd2`, `int_products__scd2` (history), `int_orders__enriched` (status, reportability, membership, attribution, first order), `int_order_items__priced` (point-in-time cost, coupon allocation, refunds), `int_sessions__funnel` |
| `models/marts/dims/` | 9 dimensions: date, customer (SCD2), product (SCD2), geography, channel, campaign, payment method, device, experiment |
| `models/marts/facts/` | 11 facts: orders, order items, payments, refunds, sessions, funnel steps, marketing spend, support tickets, subscriptions, experiment exposures, customer-monthly |
| `models/marts/analytics/` | Wide marts for BI: customer LTV, cohort retention, channel economics, product monthly, funnel daily |
| `models/metrics/` | **The governed metric layer:** `metrics_daily`, `metrics_daily_by_dimension`, `metrics_monthly`, `metric_catalog` |
| `tests/*.sql` | Singular tests: no fan-out, SCD2 no overlap, retention M0 = 100%, SRM check, raw duplicate rate, unexpected metric shift, freshness, payment reconciliation |
| `target/`, `logs/`, `dbt_packages/` | dbt build output (ignored by Git) |

### `python/nova/`: Steps 4–5, analyse and serve

| Package | Files | What it does | Writes |
|---|---|---|---|
| `common/` | `db.py` | Database connection, `read_sql()`, fast `write_df()` (COPY) | – |
| | `report.py` | Markdown table helper, writes `reports/*.md` | reports/ |
| | `data_dictionary.py` | Builds `docs/04_data_dictionary.md` from the live warehouse + dbt YAML | docs/ |
| | `charts.py` | Builds the README PNG charts | docs/images/ |
| `dq/` | `collect_dbt_results.py` | Saves dbt test outcomes | `dq.dbt_test_results` |
| | `scorecard.py` | 17 threshold checks over 6 DQ dimensions → score and verdict | `dq.dq_checks`, `dq.dq_scorecard`, report |
| `analytics/` | `descriptive.py` | Distributions, CIs, bootstrap, Mann-Whitney, Wilson CIs, censoring bias, mix vs rate | report |
| | `experiments.py` | SRM, balance, z-test, Newcombe CI, power/MDE, Welch + bootstrap, CUPED, Holm/BH, ship decision | `analytics.experiment_*`, report |
| | `causal.py` | Membership effect: naive → regression → matching → diff-in-diff | `analytics.causal_membership_estimates`, report |
| | `segmentation.py` | RFM scoring + out-of-sample validation + actions | `analytics.customer_segments`, report |
| | `forecast.py` | 4 models, rolling-origin backtest, 13-week forecast with intervals | `analytics.revenue_forecast`, report |
| | `run_all.py` | Runs the five above | – |
| `anomaly/` | `detectors.py` | Robust same-weekday z, STL residual z, quasi-binomial z for rates | – |
| | `run.py` | Level 1 (top-line) + Level 2 (segment scan), incidents, classification, drill-down, evaluation vs ground truth | `analytics.anomaly_*`, report |
| `simulator/` | `engine.py` | Unit-economics scenario model + Monte Carlo, with observed/assumption/forecast/estimate labels | `analytics.scenario_*`, report |
| `copilot/` | `planner.py` | Question → metric + periods, or a refusal (ungoverned metric / out of range) | – |
| | `tools.py` | Read-only governed tools returning evidence (compare, breakdown, anomalies, DQ, forecast) | – |
| | `prompts.py`, `llm.py` | LLM system prompt and providers (offline / Anthropic / Ollama) | – |
| | `validator.py` | Rejects answers with ungrounded numbers, unknown metrics or missing citations | – |
| | `assistant.py` | Wires it together (with a template fallback) | – |
| | `evals.py` | 13 question tests + 5 adversarial tests | report |
| | `app.py` | Streamlit chat UI | – |
| `dashboard/` | `export.py` | Builds the 6-page HTML dashboard from the warehouse, then calls the CSV exporter | `powerbi/dashboard/…html` |
| | `pbi_spec.py` | The curated list of tables and relationships for the Power BI dataset | – |
| | `export_powerbi_data.py` | Writes `powerbi/data/*.csv` + `schema.json` (typed, no raw PII) | `powerbi/data/` |

### `sql/`

| Path | Purpose |
|---|---|
| `analysis/01…27_*.sql` | 27 interview-grade queries. Each starts with: business question → why it works → why written this way → performance → how to scale. See `analysis/README.md` for the index |
| `performance/01_correlated_exists_vs_join.sql` | Real EXPLAIN case study (24.8 s → 0.18 s) |
| `performance/02_indexes_partitioning.sql` | Indexes, BRIN, monthly partitioning demo |
| `performance/README.md` | Tuning log and how to scale to 1 billion rows |

Run any query with `docker exec -i nova_pg psql -U nova -d nova < sql/analysis/05_cohort_retention_from_scratch.sql`, or open it in VS Code SQLTools / pgAdmin.

### `reports/` (generated, committed)

| File | Made by | Read it for |
|---|---|---|
| `data_quality_scorecard.md` | Step 6 | Can we trust the data? |
| `statistical_analysis.md` | Step 7 | Distributions, CIs, sampling traps |
| `experiment_readouts.md` | Step 7 | A/B test decisions |
| `causal_membership.md` | Step 7 | Correlation vs causation |
| `customer_segmentation.md` | Step 7 | RFM segments and actions |
| `revenue_forecast.md` | Step 7 | Forecast and backtest |
| `anomaly_detection.md` | Step 8 | Incident cards, evaluation |
| `decision_simulator.md` | Step 9 | Scenario estimates |
| `copilot_evaluation.md` | Step 10 | AI grounding evidence |

### `powerbi/`

| Path | Purpose |
|---|---|
| `dashboard/NovaCommerce_Dashboard.html` | **The finished 6-page interactive dashboard.** Open it in a browser |
| `dashboard/template.html` | Its source code (HTML/CSS/JS). `make dashboard` injects fresh data |
| `data/*.csv` + `schema.json` | Power BI data pack (32 tables) for building the `.pbix` without a database |
| `README.md` | Power BI build guide: connect (Postgres or CSV), relationships, model hygiene, visual checklist |
| `report_spec.md` | The 6 pages: purpose, audience, KPIs, visuals, filters, drill-downs, DAX, questions, actions |
| `dax_measures.md` | All DAX measures (revenue, margin, customers, funnel, marketing, DQ, simulator) |
| `theme.json` | Import in Power BI: View → Themes → Browse |
| `power_query.m` | Parameterised PostgreSQL connection |
| `screenshots/` | Page images for the README / LinkedIn |

### `docs/`

| File | What it is |
|---|---|
| `00_project_strategy.md` | Target roles, skills map, milestones, Definition of Done, 8-week plan, risks |
| `01_business_requirements.md` | Stakeholders, questions BR-01…BR-10, non-functional requirements |
| `02_architecture.md` | Architecture diagram, layer rules, the SQL vs Python split |
| `03_data_model.md` | ERD, grain of each fact, SCD decisions |
| `04_data_dictionary.md` | Every column of every mart/metric table (generated) |
| `05_metric_definitions.md` | **Most important doc:** each metric's definition, formula, SQL, filters, edge cases, common mistakes |
| `06_data_quality.md` | DQ framework and the defect register |
| `08_executive_memo.md` | The one-page memo to leadership |
| `09_scaling_and_production.md` | How this becomes production, 1B rows, monitoring |
| `decisions/ADR-00x-*.md` | Why Postgres, dbt, raw-as-TEXT, pre-filtered measures, no Airflow, a grounded copilot |
| `10_interview_preparation.md` | 131 questions with model answers |
| `11_career_assets.md` | Resume bullets, LinkedIn/GitHub text, pitches, STAR story |
| `images/` | README charts |

### `tests/`

| File | Checks |
|---|---|
| `test_generator.py` | Same seed → identical data. The defects really exist |
| `test_copilot_validator.py` | Invented numbers, metrics and uncited claims are rejected |
| `test_planner.py` | "last month" = Dec 2025, NPS/GMV refused, quarters parsed |
| `test_anomaly_detectors.py` | A spike is detected, weekday patterns are not, rate tests are volume-aware |
| `test_simulator.py` | Model behaves logically (better retention → more customers) |

---

## 5. Follow one order through the system

This is the best way to understand the architecture, and a great interview story. The order below is an *illustrative* example of what the pipeline does to every real row.

1. **Generated** (`commerce.py`). Imagine a customer in Lucknow who places an order at 23:40 IST on 14 Nov 2025 on the app, paying by UPI. App v5.2.0 is live, so the first UPI attempt fails (`upi_intent_launch_failed`); the retry succeeds.
2. **Written as CSV** (`run.py`). `orders.csv` stores the time in **UTC**: `2025-11-14 18:10:00`. `payments.csv` has two rows (failed, success). `defects.py` may also have written a duplicate row with a later `_extracted_at`.
3. **Loaded** (`load_raw.py`) into `raw.orders` as TEXT, with `_batch_id = 2026-01-01`.
4. **Staged** (`stg_orders.sql`). Converted to IST (`2025-11-15 00:10` → it is a **15 Nov** order). The duplicate is removed (latest extract wins). `payment_method` "upi" → "UPI" through the seed mapping.
5. **Enriched** (`int_orders__enriched.sql`). Marked `is_completed`, `is_reportable`. Attribution comes from the session's UTM. Membership is checked. `customer_order_number` is computed.
6. **Priced** (`int_order_items__priced.sql`). Each line gets the product cost **valid on that date** (SCD2), and the coupon is split across lines.
7. **Fact** (`fct_orders.sql`). Governed columns: `net_revenue = gross − coupon − refunds`, then `contribution_margin`. Its two payment attempts sit in `fct_payments`.
8. **Metrics** (`metrics_daily.sql`). Added into 15 Nov's net revenue, orders and payment attempts (1 of 2 successful).
9. **Tested.** `sum_reconciles` proves the three revenue totals agree. `unique` proves there's no duplicate.
10. **Analysed** (`anomaly/run.py`). The weekly segment scan sees mobile-app payment success collapse, and the drill-down points to Uttar Pradesh + UPI.
11. **Shown.** Dashboard page 4 (payment chart) and page 5 (incident card). The Copilot answers "What happened to payment success in November 2025?" with cited evidence.

---

## 6. Build the Power BI dashboard

You have three levels:

1. **Ready now:** `powerbi/dashboard/NovaCommerce_Dashboard.html`. It has 6 pages, period presets, filters, drill-down charts and a live simulator, all using the governed data. Use it in demos and as the blueprint.
2. **Build the `.pbix`** (Windows, about 2–3 hours):
   - Follow `powerbi/README.md`. Import `powerbi/data/*.csv` (or connect to Postgres), create the relationships, mark `dim_date` as the date table, and apply `theme.json`.
   - Add the measures from `powerbi/dax_measures.md` (copy them folder by folder).
   - Build each page from `powerbi/report_spec.md`, copying the layout of the HTML dashboard.
   - Save as `powerbi/NovaCommerce.pbix`, export page PNGs to `powerbi/screenshots/`.
3. **Optional:** publish to Power BI Service (free account) and put the link in the README.

---

## 7. Publish: GitHub and LinkedIn

```bash
git init
git add .
git commit -m "NovaCommerce decision intelligence platform"
git branch -M main
git remote add origin https://github.com/<your-username>/nova-commerce-analytics.git
git push -u origin main
```

- `.gitignore` already excludes secrets (`.env`), generated CSVs (`data/landing`) and dbt build output.
- `powerbi/data/` is about 50 MB. Keep it if you want recruiters to open Power BI without running anything, or add `powerbi/data/` to `.gitignore` to keep the repo light. Either is fine.
- GitHub → About: paste the description and topics from `docs/11_career_assets.md`.
- **Live dashboard link (free):** Settings → Pages → deploy from `main`. Your dashboard is then at `https://<user>.github.io/nova-commerce-analytics/powerbi/dashboard/NovaCommerce_Dashboard.html`. Put that link at the top of the README and in LinkedIn.
- Check the **Actions** tab. The CI run should be green.
- LinkedIn post and resume bullets: `docs/11_career_assets.md`. Always say the data is synthetic and the impact is simulated.

---

## 8. Learning path: how to study this for interviews

| Week | Read / do | You should be able to… |
|---|---|---|
| 1 | README → this guide → `docs/01`, `02`. Run `make all` yourself | Explain the architecture in 2 minutes |
| 2 | `generator/scenarios.py`, `defects.py`, `ingestion/load_raw.py`, `docs/decisions/` | Explain why raw is TEXT and why loads are idempotent |
| 3 | `models/staging` → `intermediate`, `docs/03_data_model.md` | Explain every grain and the SCD2 point-in-time join |
| 4 | `docs/05_metric_definitions.md`, `models/metrics/` | Define net revenue, CM, CAC and LTV, and 3 ways each goes wrong |
| 5 | `sql/analysis/` (retype 10 queries), `sql/performance/` | Write cohort retention and top-N from memory. Read EXPLAIN |
| 6 | `reports/experiment_readouts.md`, `causal_membership.md`, `statistical_analysis.md` | Defend SRM, power, CUPED, and why DiD is an upper bound |
| 7 | `reports/anomaly_detection.md`, the Copilot code, build the Power BI | Explain "averages hide problems" and how hallucination is prevented |
| 8 | `docs/10_interview_preparation.md` (mock interviews), `docs/11_career_assets.md` | Answer the 31 project-defence questions without notes |

**Rule:** for every file, be able to answer "what does it do, why does it exist, and what breaks if I delete it?"

---

## 9. Troubleshooting

| Problem | Fix |
|---|---|
| `docker: command not found` / cannot connect | Start Docker Desktop, then wait until it says *running* |
| `port 5432 already in use` | Another PostgreSQL is running. Stop it, or change the port in `docker-compose.yml` and `.env` (`PGPORT`) |
| `ModuleNotFoundError: nova` | Run from the project root with `PYTHONPATH=python` (the Makefile sets it). PowerShell: `$env:PYTHONPATH="python"` |
| `make: command not found` (Windows) | Use the PowerShell commands shown under each step |
| `dbt deps` SSL / network error | Behind a corporate proxy, set `REQUESTS_CA_BUNDLE` to your CA file, or run on a home network. `dbt_utils` must download once |
| dbt `could not connect to server` | `.env` values must match `docker-compose.yml`. Run `docker ps` to check `nova_pg` is healthy |
| dbt shows `WARN=8` | Expected: those are the planted defects. Only `ERROR>0` is a problem |
| `relation "dq.dq_scorecard" does not exist` | You skipped a step. Run `make dq` (or `make all`) |
| The dashboard HTML is blank | It needs internet once to load Chart.js from jsDelivr. Open it in Chrome or Edge |
| Power BI: dates are text | In Power Query, set column type to *Date* (the `schema.json` lists the intended types) |
| Want a fresh start | `make clean`, then `docker compose -f docker/docker-compose.yml down -v`, then `make db-up all` |

---

## 10. Command cheat-sheet

| Command | Does |
|---|---|
| `make help` | list all commands |
| `make setup` | install Python packages |
| `make db-up` / `make db-down` | start / stop PostgreSQL |
| `make generate` | create the source CSVs |
| `make ingest` | load CSVs → `raw` |
| `make dbt-build` | build + test all dbt models |
| `make dbt-docs` | open the dbt lineage/documentation site |
| `make dq` | data-quality scorecard |
| `make analytics` | stats, experiments, causal, RFM, forecast |
| `make anomalies` | anomaly detection |
| `make simulate` | decision simulator |
| `make copilot-eval` / `make copilot-app` | test / open the AI Copilot |
| `make docs` | regenerate the data dictionary + charts |
| `make dashboard` | rebuild the HTML dashboard + Power BI CSVs |
| `make all` | everything, from generate to dashboard |
| `make test` / `make lint` | unit tests / code style |
| `make sample` + `make ci` | the small CI run |
| `make clean` | delete generated data and dbt output |
