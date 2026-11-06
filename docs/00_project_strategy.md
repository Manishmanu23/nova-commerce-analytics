# Project Strategy, Plan and Definition of Done

## Strategy

The project is positioned as the work of a small internal analytics team, not as a dashboard. The narrative runs from an ambiguous executive question to trustworthy data, one definition per metric, careful analysis, and decisions that are honestly caveated.

**Key design choice: synthetic data with planted ground truth.** Six business scenarios (S1–S6) and about 20 real-world defects are injected by a seeded generator. Every method (anomaly detection, experiment analysis, causal adjustment, de-duplication) is then *validated* by checking that it recovers what we know is there. With real data you can never check this.

## Target roles and what each is shown

| Role | Screens for | Evidence in this repo |
|---|---|---|
| Data Analyst | SQL, BI, KPIs | `sql/analysis/` (27 queries), Power BI spec, metric definitions |
| Senior Data Analyst | Ambiguity, rigour, stakeholder framing | Business requirements, metric governance, experiment readouts, memo |
| BI Analyst | Modelling, DAX, governance | Star schema, SCD2, DAX library, 6-page spec |
| Product Analyst | Funnels, A/B tests, retention | Funnel models, SRM/CUPED/power, cohorts |
| Business Analyst | Requirements, decision support | BR-01…BR-10, decision simulator |
| Analytics Engineer (adjacent) | dbt, tests, CI | dbt layers, 125 tests, custom generic tests, GitHub Actions |

## Skills → project mapping

| Skill | Where |
|---|---|
| Advanced SQL | dbt models, `sql/analysis`, `sql/performance` |
| Python / pandas | generator, ingestion, `nova.analytics`, `nova.anomaly`, `nova.simulator`, `nova.copilot` |
| Data modelling | `docs/03_data_model.md`, marts |
| ETL/ELT | `ingestion/load_raw.py` + dbt |
| Data quality | dbt tests, `nova.dq.scorecard` |
| Statistics / experimentation | `reports/statistical_analysis.md`, `reports/experiment_readouts.md`, `reports/causal_membership.md` |
| Customer / product / revenue analytics | cohort, LTV, RFM, waterfall, product marts |
| Storytelling | README, `docs/08_executive_memo.md` |
| Cloud / warehouse concepts | `docs/09_scaling_and_production.md`, partitioning/BRIN/incremental |
| AI-assisted analytics | Copilot with grounding validator and eval suite |

## Milestones (as delivered)

| Phase | Deliverable | Status |
|---|---|---|
| 1 | Environment, requirements, seeded generator with scenarios and defects | done |
| 2 | Idempotent ingestion, raw layer, audit, contracts | done |
| 3 | dbt staging + intermediate, SCD2, tests | done |
| 4 | Star schema, metric layer, catalogue, data dictionary | done |
| 5 | SQL analysis library + performance case studies | done |
| 6 | Statistics, experiments, causal, segmentation, forecast | done |
| 7 | Anomaly detection (2 levels) + DQ scorecard | done |
| 8 | Power BI spec + DAX + decision simulator | spec done. Build the `.pbix` locally |
| 9 | Analytics Copilot + evaluation | done |
| 10 | README, memo, interview prep, career assets | done |

## 8-week execution plan (for someone rebuilding or extending this)

| Week | Focus | Checkpoint |
|---|---|---|
| 1 | Read the generator, run `make all`, study `docs/01-03` | Can explain every grain and why it was chosen |
| 2 | Ingestion + staging: break things on purpose (remove a column, re-run a file) | Can explain idempotency and raw-as-TEXT |
| 3 | Intermediate + marts: SCD2, attribution, coupon allocation | Can rebuild retention from scratch (`sql/analysis/05`) |
| 4 | Metric governance: rewrite each definition in your own words | Can list three wrong ways to compute each metric |
| 5 | SQL library: re-type every query, then optimise one | Can explain EXPLAIN output |
| 6 | Stats + experiments + causal | Can defend SRM, CUPED, power and the upper-bound argument |
| 7 | Build the Power BI report from the spec | 6 pages, screenshots committed |
| 8 | Mock interviews with `docs/10_interview_preparation.md` | Can answer the 31 defence questions without notes |

## Definition of Done (project level)

- [x] `make all` rebuilds everything from a clean database. `dbt build`: 0 errors, and the warnings are exactly the documented defects
- [x] Every fact has a written grain. The data dictionary is generated from the warehouse
- [x] Every certified metric has a definition, formula, SQL, grain, filters, exclusions, edge cases and common mistakes
- [x] Net revenue reconciles across three models (dbt test)
- [x] The planted scenarios are recovered by the methods, not hard-coded (the anomaly evaluation table, the experiment SRM result, the causal estimates)
- [x] Every statistical result states what a stakeholder should and should not conclude
- [x] Simulator outputs are labelled observed / assumption / forecast / estimate
- [x] Copilot: 0 ungrounded numbers on the eval suite. Adversarial drafts are rejected
- [x] CI: lint + dbt build on a sample + pytest
- [ ] Power BI `.pbix` built and screenshots committed (your step)

## Risks and common mistakes (and how the project avoids them)

| Risk | Mitigation here |
|---|---|
| Too-clean data, so no insight | Planted scenarios, realistic distributions and defects |
| Business logic in DAX | Governed columns, and DAX that only sums them |
| Revenue defined three ways | Catalogue + reconciliation tests |
| Fan-out joins | Grain discipline + `assert_no_fanout_order_items` |
| Anomaly treated as a cause | "Localises, doesn't prove" appears on every card |
| p-hacking | Pre-registered MDE, SRM first, Holm/BH |
| LLM inventing numbers | Tool-only data access + validator + evals |
| Fake business impact | Everything is labelled simulated |

## Interview value of each component

| Component | What it proves | Question it prepares you for |
|---|---|---|
| Planted-scenario generator | Method validation mindset | "How do you know your analysis is right?" |
| Idempotent ingestion | Engineering maturity | "What if the job runs twice?" |
| dbt layers + tests | Analytics engineering | "Why staging vs marts?" |
| Grain + SCD2 | Modelling depth | "Customer moved city: which state gets last year's revenue?" |
| Metric governance | Senior judgement | "Two teams report different revenue: what do you do?" |
| SQL + EXPLAIN | Technical depth | "Optimise this for 1B rows" |
| Experiments | Rigour | "It's significant, do we ship?" |
| Two-level anomaly detection | Monitoring mindset | "Revenue looks fine but orders are failing somewhere: how would you know?" |
| DQ scorecard | Trust | "Why should leadership trust this?" |
| Simulator | Business partnership | "What if we cut discounts?" |
| Copilot | Responsible AI | "How do you stop hallucinations?" |
