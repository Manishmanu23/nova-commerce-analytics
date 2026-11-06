# 11. Career Assets: How to Present This Project

This document contains ready-to-use material for resumes, LinkedIn, GitHub and interviews. It is written for Data Analyst, Senior Data Analyst, BI Analyst, Product Analyst and analytics-engineering-adjacent roles in the Indian job market.

**Ground rule:** every number here comes from a **synthetic, simulated** dataset: 30,000 registered customers, about 60k orders, 1.69M sessions, 2024–2025, INR. Always label it that way. Recruiters and hiring managers in India see many inflated portfolio claims, and honesty stands out. Claiming business impact from a portfolio project is the quickest way to lose credibility in a technical round.

---

## 1. Resume bullets

Use all three under a "Projects" heading, or pick two for a one-page resume. Each starts with an action, names the stack, quantifies the work, and labels results as simulated.

- **Built an end-to-end revenue analytics platform** (Python, PostgreSQL, dbt, Power BI) on a synthetic 60k-order Indian D2C e-commerce dataset. The platform has idempotent SHA-256-audited ingestion, a star schema of 11 facts and 9 dimensions with SCD2, and about 180 dbt tests. It handles 20+ injected data defects (duplicate batches, UTC/IST shifts, paise/INR mix-ups, bot traffic), with a DQ scorecard of 86.2/100 and one governed metric layer shared by BI, anomaly detection and an AI copilot.
- **Diagnosed a simulated margin decline:** contribution margin fell from 23.6% to 16.5% during a deep-discount campaign. I showed that the cheapest-CAC campaign (₹359 against ₹800–1,200) had the weakest 90-day repeat rate (32% against 45–55%) and a CM payback of 0.59. A segment-level anomaly scan found an app-release UPI payment failure hidden in national averages (state-level success about 90% → 50%).
- **Applied experimentation and causal inference** (SRM, CUPED, Welch and bootstrap, Holm/BH, matching, diff-in-diff) to three simulated A/B tests and a membership programme. The work invalidated a test with an inflated +28% lift (SRM p = 4e-10) and cut a naive +439% membership effect to a +51% upper bound. I also built a grounded LLM copilot whose validator rejects any ungrounded number, and it passed 13/13 evals, including prompt injection.

Shorter variants, one line each, for crowded resumes:

- Built a Python → PostgreSQL → dbt → Power BI analytics platform with about 180 data tests and SCD2 star schema on a synthetic 60k-order e-commerce dataset.
- Found the drivers of a simulated margin drop (discount-led acquisition, app payment failures, supplier quality) using cohort, funnel and segment-level anomaly analysis.
- Ran experiment readouts with SRM, power and CUPED checks, and estimated membership impact with matching and diff-in-diff (simulated data).

Keyword line for ATS (put in a Skills section, not the bullets): SQL (PostgreSQL, window functions, CTEs), dbt, Python (pandas, NumPy, SciPy, statsmodels), Power BI (DAX, data modelling, RLS), dimensional modelling, SCD Type 2, data quality, A/B testing, causal inference, cohort analysis, forecasting, Git, GitHub Actions, Docker.

---

## 2. LinkedIn project description

For the Projects section, or as a featured post with screenshots from `powerbi/screenshots/`.

> **NovaCommerce Decision Intelligence & Revenue Analytics Platform**
>
> An end-to-end analytics project built around one executive question: *why is profitable growth changing, which customers, products and channels are driving it, what risks are emerging, and what should leadership do?*
>
> The business is a fictional Indian D2C e-commerce and subscription brand selling via web, app and marketplaces. The data is synthetic: 30k customers, about 60k orders and 1.69M sessions over 2024–2025. I generated it with realistic defects (duplicate batches, timezone shifts, paise vs rupee amounts, bot traffic, late refunds, orphan records) and planted business scenarios, so I could check whether my methods find the right answers.
>
> **What I built:**
> - Idempotent Python ingestion with file-hash auditing, data contracts and schema-drift handling into PostgreSQL
> - A dbt project with staging, intermediate, a star schema (SCD2 customers and products) and a governed metrics layer, with about 180 tests
> - Analysis in SQL and Python: cohort retention, LTV:CAC by channel, funnel and payment diagnostics, RFM, forecasting
> - Experiment readouts (SRM, power, CUPED, multiple-testing correction) and a causal study of a membership programme
> - A two-level anomaly detection system and a data-quality scorecard
> - A decision simulator with Monte Carlo ranges, and an Analytics Copilot whose answers are validated against governed evidence, so it cannot invent numbers
> - A 6-page Power BI report
>
> **What the analysis found (simulated):** revenue grew 70% but margin quality slipped during a deep-discount campaign. The cheapest-CAC campaign brought the least loyal customers. An app release broke UPI payments in three states while national metrics looked fine. An A/B test with a +28% "win" was invalid because of a sample ratio mismatch.
>
> **Stack:** Python, PostgreSQL 16, dbt-core, Power BI (DAX), Docker, GitHub Actions, pytest.
>
> All figures are from simulated data and demonstrate method, not real business impact.

---

## 3. GitHub repository

**Description (under 350 characters):**

> End-to-end revenue analytics on synthetic Indian D2C e-commerce data: Python ingestion → PostgreSQL → dbt star schema (SCD2, ~180 tests, governed metrics) → experiments, causal inference, anomaly detection, DQ scorecard, decision simulator, grounded LLM copilot and Power BI. Reproducible with `make all`.

**Suggested topics/tags:**

`data-analytics`, `analytics-engineering`, `dbt`, `postgresql`, `sql`, `python`, `power-bi`, `dax`, `data-modeling`, `star-schema`, `scd2`, `data-quality`, `ab-testing`, `causal-inference`, `anomaly-detection`, `forecasting`, `ecommerce-analytics`, `cohort-analysis`, `synthetic-data`, `llm`, `github-actions`, `docker`

**README tips:**

- Put the executive question and a dashboard screenshot at the top.
- Add a "Key findings (simulated)" block with 4–5 bullets.
- Include an architecture diagram and a one-command quickstart (`make all`).
- Link to `docs/10_interview_preparation.md`, the reports in `reports/`, and the dbt docs.
- Pin the repository on your GitHub profile.

---

## 4. 30-second pitch

> "I built an end-to-end analytics platform for a fictional Indian D2C e-commerce brand, from raw data to a Power BI dashboard, using Python, PostgreSQL and dbt. The data is synthetic, but deliberately messy, with things like duplicate batches, timezone shifts and bot traffic, and I planted real business problems in it to test whether my methods could find them. They did. For example, I showed that the campaign with the cheapest customer acquisition cost brought in the least loyal customers. I also found an app bug that broke UPI payments in three states while the national numbers looked normal."

---

## 5. 2-minute pitch

> "The project answers one question a leadership team would ask: why is profitable growth changing, and what should we do about it?
>
> I set it up as a fictional Indian D2C brand with a membership programme, selling via web, app and marketplaces. I generated two years of synthetic data, about 60,000 orders and 1.7 million sessions, and deliberately injected the problems real data has: duplicate order batches, UTC versus IST timestamps, marketplace amounts in paise, webhook replays, late refunds and a bot spike. I also planted business scenarios so I could check my analysis against a known truth.
>
> On the engineering side, I built idempotent ingestion into PostgreSQL with file-hash auditing and data contracts. The dbt project has a star schema, slowly changing dimensions for customer location and product cost, and about 180 tests. The key design decision was a governed metric layer: net revenue, contribution margin and so on are defined once, and Power BI, the anomaly detector and an AI copilot all read the same numbers.
>
> On the analysis side, in the simulated data, revenue grew 70% but contribution margin dropped from about 24% to 16.5% during a deep-discount Meta campaign. That campaign had the lowest CAC, ₹359, but only 32% of its customers came back within 90 days, against around 50% for other campaigns. A segment-level anomaly scan found that an app release had broken UPI payments in Uttar Pradesh, Bihar and West Bengal, while the national payment rate barely moved. For experiments, I caught a test showing a +28% lift that was invalid because of a sample ratio mismatch. And I showed that the membership programme's apparent 4× effect was mostly self-selection.
>
> Finally, I translated this into decisions: a simulator that compares options like a retention programme versus stopping deep discounts, with uncertainty ranges, and a copilot that can answer questions but cannot state a number the system didn't compute."

---

## 6. 5-minute presentation (7 slides)

Aim for about 40 seconds per slide, with time for one question. Use dashboard screenshots where possible, and keep text on slides minimal.

### Slide 1: The question

- **On screen:** "Why is profitable growth changing, what is driving it, what risks are emerging, and what should we do?" Plus a one-line business description (fictional Indian D2C brand, web, app and marketplace, Nova Plus membership, INR, 2024–2025, synthetic data).
- **Talking points:** "This is the question a CEO or CFO actually asks. Everything in the project exists to answer it credibly. The data is synthetic, and I'll explain why that's a strength for validating methods."

### Slide 2: Architecture and trust

- **On screen:** a pipeline diagram (generator → ingestion → Postgres raw → dbt staging, intermediate, marts, metrics → analytics, anomaly, DQ, simulator, copilot → Power BI), with key counts: 16 source tables, about 180 tests, DQ 86.2/100.
- **Talking points:** "Raw is all TEXT and loaded idempotently with SHA-256 auditing. dbt handles casting, deduplication and business logic. Governed measures are pre-zeroed for non-countable orders, so SUM is always right. One metric layer feeds every consumer. The duplicate batch on 18 March 2025 doubles raw revenue but never reaches the dashboard, and I can prove it with a layered reconciliation."

### Slide 3: Growth changed quality

- **On screen:** a monthly net revenue and CM% chart. Net revenue ₹4.19 Cr → ₹7.13 Cr (+70%). CM% 23.6% in H1 2025, 16.5% in Aug–Oct, 20.8% in Nov–Dec. Coupon rate 1.5% → 4.9% of gross. Label: simulated.
- **Talking points:** "Top-line growth looks great. But in Aug–Oct margin fell sharply, and CM after marketing halved from 19.3% to 9.6%. The waterfall shows it was discounts, not COGS or logistics."

### Slide 4: The cheapest customers were the least valuable

- **On screen:** a campaign comparison. Social Blitz CAC ₹359 against ₹800–1,200, 90-day repeat 32% against 45–55%, 90-day CM per customer ₹212, CM payback 0.59. LTV:CAC by channel: marketplace 1.93, affiliate 1.75, paid search 1.55, paid social 1.41.
- **Talking points:** "A 40% first-order discount attracted deal-seekers. CAC alone would have told us to scale it. Mature-cohort LTV says the opposite. Caveat: attribution is last-touch, so these are directional. I'd validate with a lift test."

### Slide 5: Risks hidden in averages

- **On screen:** a small-multiples chart. National payment success is flat, while app payment success drops from 89.1% to 76.9%, and in Uttar Pradesh, West Bengal and Bihar from about 90% to about 50% after release 5.2.0. Plus the VoltEdge refund trend: about 3% → 14% → 18% by quarter.
- **Talking points:** "The national metric never crossed an alert threshold. The weekly segment scan flagged it with a z-score of 7.8, and the drill-down pointed to UPI in three states: about 64 extra failed orders and ₹1.5 lakh at risk before the hotfix. VoltEdge is a slow drift, so it needs trend monitoring, not anomaly alerts. Matching the tool to the failure mode is the point."

### Slide 6: What we can and cannot conclude

- **On screen:** a table of experiments: EXP-01 +9.5% (CI +1.0% to +18.8%), power 21%, SHIP WITH MONITORING. EXP-02 SRM p = 4e-10, INVALID. EXP-03 INCONCLUSIVE. Membership estimator ladder: naive +439%, regression +392%, matching +215%, DiD +51%.
- **Talking points:** "Rigour means saying no. The +28% free-shipping result is invalid because of broken assignment. Membership looks like a 4× effect, but most of it is selection. My best estimate is an upper bound, so I recommend a randomised encouragement test before investing."

### Slide 7: Recommendations and decision support

- **On screen:** simulator results over 12 months (CM after marketing, simulated, with P10/P90): retention programme +₹6.8L, stop deep-discount acquisition +₹6.3L, fix app payments +₹5.2L, price +3% +₹2.7L. Three asks: a shallower-discount test, a staged-release gate on payment success, and a membership encouragement experiment. Plus a Copilot screenshot with evidence citations.
- **Talking points:** "The top options have overlapping ranges, so choose on cost and certainty. Fixing payments is cheap and certain, so do it now. Every assumption is labelled observed, assumption, forecast or estimate. The copilot lets leaders ask follow-ups, but it can't invent a number. It passed 13 of 13 evals, including a prompt injection."

---

## 7. STAR-format project story

Use this for "Tell me about a project you're proud of" or "Tell me about a complex analysis."

**Situation.** I wanted a portfolio project that reflected what analysts actually face in Indian e-commerce: messy multi-source data, conflicting definitions, and leadership asking "why" rather than "what". Public datasets are too clean and have no known answers. So I designed a fictional D2C brand with a membership programme and generated two years of synthetic data (about 60k orders and 1.69M sessions), with realistic defects and planted business scenarios.

**Task.** Answer the executive question, "why is profitable growth changing, what is driving it, what risks are emerging, and what should we do?", with numbers that leadership could trust, and prove that my methods would find problems I had planted without looking at the answers.

**Action.**

- I built idempotent ingestion into PostgreSQL (SHA-256 file auditing, data contracts, schema-drift handling, all-TEXT raw layer).
- I modelled a dbt star schema with SCD2 dimensions and a governed metric layer. Measures are pre-zeroed for non-countable orders so a simple SUM is always correct. I wrote about 180 tests, including invariants such as month-0 retention = 100%, no fan-out and payment reconciliation.
- I analysed profitability with a margin waterfall, channel economics on mature cohorts, cohort retention and repeat rates.
- I built a two-level anomaly system: top-line robust z-scores with sale days masked, plus a weekly segment scan with over-dispersion-corrected rate tests.
- I read out three experiments with SRM, power, CUPED and multiple-testing corrections, and estimated the membership effect with four increasingly credible methods.
- I turned the findings into a decision simulator with Monte Carlo ranges, a Power BI report, and a copilot with a grounding validator.

**Result (all simulated).**

- **Margin:** revenue grew 70%, but CM% fell from 23.6% to 16.5% during a 40%-discount Meta campaign. That campaign had the lowest CAC (₹359) but a 32% 90-day repeat rate and a CM payback of 0.59.
- **Payments:** the segment scan found the app-release UPI failure (success about 90% → 50% in three states) that the national metric missed.
- **Experiments:** I invalidated an experiment showing +28% because of SRM (p = 4e-10).
- **Membership:** I reduced the naive +439% effect to a +51% upper bound and recommended an encouragement experiment.
- **Data quality:** 86.2/100, with every warning traced to a known, mitigated defect.
- **Copilot:** it passed 13/13 end-to-end evals and 5/5 adversarial validator tests.

**Reflection** (senior interviewers value this). The causal methods did not fully recover the true effect, which reinforced that observational estimates need a stated bias direction. If I rebuilt it, I would put metrics in a semantic layer and use incremental models from day one.

---

## 8. How to talk about synthetic data honestly

- **Say it first, not when caught.** "The data is synthetic, and I generated it deliberately." Put it on the resume, README, LinkedIn and first slide.
- **Frame it as a validation design.** "Because I planted scenarios with known answers, I could test whether my methods recover them. With real data you rarely know the right answer."
- **Separate method from impact.** Say "the analysis identified" or "in the simulation", never "I increased", "I saved" or "I drove". There is no real business impact, and claiming any is misrepresentation.
- **Name what it cannot show.** Synthetic data only contains the messiness I imagined. Real sources have surprises, political constraints and stakeholders. I would acknowledge that and connect it to any real experience you have, such as internships, work projects or college projects.
- **Show that you did not just find your plants.** Mention the unflattering results: causal methods overestimate (+51% against a true +15%), EXP-01 is underpowered at 21% power, there are 3 false-positive business signals, and the forecast has −13% bias. They show the analysis was not reverse-engineered.
- **Keep the labels.** Every chart and number in the deck and dashboard carries "simulated". Forecasts carry "FORECAST", and simulator outputs are labelled observed, assumption, forecast or estimate.
- **If asked "why not real data?":** "Real e-commerce data with orders, sessions, payments, refunds, spend and experiments linked together is not public, and company data would be confidential. Synthetic data let me build the full system and prove correctness. I'm keen to apply the same approach to real data."

---

## 9. Tailoring by role

Indian hiring loops for these roles commonly include a SQL screen (often live or on a platform such as HackerRank), a case or guesstimate round, a tools round (Power BI, Excel or Python), and a hiring-manager or bar-raiser round. Tailor what you lead with.

### Data Analyst

- **Lead with:** business findings and SQL. The Social Blitz CAC-vs-repeat story, the margin waterfall, cohort retention.
- **Emphasise:** clean governed metrics, the Power BI dashboard, `sql/analysis/` (27 queries covering windows, cohorts, gaps and islands, top-N, RFM, Pareto).
- **De-emphasise:** the copilot internals, SCD2 mechanics, CI.
- **Resume focus:** bullet 2 first, then bullet 1 (shortened).
- **Prepare:** SQL-1 to SQL-15, BC-1 to BC-5, PBI-3/4/6.

### Senior Data Analyst

- **Lead with:** judgement and stakeholder framing. "Averages hide problems" (S2), "the cheapest campaign was the least valuable", and saying no to the invalid +28% experiment.
- **Emphasise:** metric governance (one definition, certified catalogue, two departments defining revenue differently), cost-of-being-wrong reasoning, recommendations with uncertainty (the simulator's P10/P90), and handling executive disagreement.
- **Resume focus:** all three bullets, with bullet 2 first.
- **Prepare:** the whole Project-defense section, especially PD-9, PD-11, PD-14, PD-16, PD-28, and BC-9/10/15.

### BI Analyst / BI Developer

- **Lead with:** the Power BI report and the model behind it. Star schema, conformed `dim_channel`, the marked date table with the Indian fiscal year, ratio measures via DIVIDE of summed components, Unknown members.
- **Emphasise:** DAX (time intelligence, what-if parameters, lakh/crore formatting), RLS, Import vs DirectQuery, incremental refresh with a 30-day window for late refunds, avoiding bidirectional filters, and dashboard trust features (DQ score, provisional flags).
- **De-emphasise:** causal inference details.
- **Prepare:** all 20 Power BI questions, SQL-2/5/6/7, PD-1, PD-9.

### Product Analyst

- **Lead with:** experiments and funnels. EXP-01 (ship with monitoring at 21% power), EXP-02 invalid because of SRM, EXP-03 inconclusive, the app-release payment funnel incident, and the membership causal ladder.
- **Emphasise:** SRM, power and MDE, CUPED, Holm/BH, guardrail metrics, the encouragement design, the rate vs mix decomposition, funnel by device, and release gating.
- **Resume focus:** bullet 3 first, then bullet 2.
- **Prepare:** all Statistics questions, PD-12/13, BC-6/8/12, SQL-24/30.

### Analytics Engineer (adjacent)

- **Lead with:** the pipeline. Idempotent ingestion (SHA-256 audit, contracts, schema drift, per-file transactions, COPY), all-TEXT raw with defensive casting macros, dbt layering, SCD2 design, pre-zeroed governed measures, and about 180 tests including custom generic and singular tests.
- **Emphasise:** CI (ruff, dbt build on a 1,500-customer sample in a Postgres service container, pytest), the performance fix (24.8 s → 0.18 s query, 36 s → 1 s model), the scaling plan to 1B rows, and why Airflow and MetricFlow are not used (and when they would be).
- **Resume focus:** bullet 1 first. Consider adding: "Cut a dbt model build from 36 s to 1 s by replacing a correlated EXISTS against a view with a set-based join (development dataset)."
- **Prepare:** PD-1 to PD-10, PD-17/18/21/23/26, SQL-3/12/13/16/17/29, PY-3/4/5.

### A note for India-specific interviews

- **Use INR conventions naturally** (₹7.13 Cr, ₹1.5 lakh). It signals domain fit for Indian D2C and quick-commerce companies.
- **Mention India-specific realities the project handles:** UPI intent failures, marketplace channels, festive seasonality (the Diwali-period peak in Oct 2025), the Apr–Mar fiscal year, city tiers, and the DPDP Act 2023 for PII.
- **Expect guesstimate or case rounds.** Practise turning the project's metric tree into one: net revenue = sessions × conversion × AOV − coupons − returns.
- **For service-company or GCC analytics roles,** stress reproducibility, testing, documentation and governance. For startups, stress speed to insight and the recommendations.
