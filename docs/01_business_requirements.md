# Business Requirements

## Context

NovaCommerce is a fictional Indian D2C brand selling Fashion, Electronics, Beauty, Home, Grocery and Sports products through its website, its mobile app and third-party marketplaces. It also sells a paid membership, **Nova Plus** (₹149/month or ₹999/year: free shipping plus member pricing). The new data platform went live on **1 Jan 2024**. Customers existed before that date, but their older order history was not migrated.

## Executive question

> *Why is profitable growth changing? Which customers, products and channels are driving the change? What risks are emerging, and what actions should leadership consider?*

## Stakeholders and their questions

| ID | Stakeholder | Decision they own | Question | Delivered by |
|---|---|---|---|---|
| BR-01 | CEO | Growth vs profitability trade-off | Is growth profitable? What moved net revenue and CM, MoM and YoY? | Power BI p1, `metrics_monthly`, `sql/analysis/01-03` |
| BR-02 | CFO | Pricing, discount policy | Where does margin leak (coupons, refunds, fulfilment, commission)? | p3, `sql/analysis/02` waterfall |
| BR-03 | CMO | Budget allocation by channel/campaign | Which channels acquire customers who pay back CAC? | p4, `mart_channel_monthly_economics`, `sql/analysis/09,16` |
| BR-04 | Head of Product | Funnel and app priorities | Where does the funnel break, and on which device/version? | p4, `mart_funnel_daily`, `sql/analysis/10-11` |
| BR-05 | Head of Product / Growth | Ship or kill experiments | Did experiments work, and can we trust them? | `reports/experiment_readouts.md` |
| BR-06 | Head of CX / Category | Supplier and quality actions | Are refunds or tickets concentrated in a product, brand or reason? | p3, `sql/analysis/13` |
| BR-07 | Data lead / everyone | Whether to trust the numbers | Is today's data fit for decisions? | p5, `dq.dq_scorecard` |
| BR-08 | Leadership | Planning | What happens to CM if we change retention, conversion, AOV, CAC, discounts or refunds? | p6, `nova.simulator` |
| BR-09 | Anyone | Fast, safe answers | "Why did metric X move?", answered with evidence only | Copilot, `analytics.anomaly_*` |
| BR-10 | CRM | Retention spend targeting | Who should we target, and with what? | `analytics.customer_segments` |

## Functional requirements

1. **One definition per metric** (see `05_metric_definitions.md`). The same number appears on every surface. This is enforced by dbt reconciliation tests.
2. **Drill-down** from any executive KPI to channel, device, state, category, customer type and campaign.
3. **Anomaly alerts** with expected vs actual values, deviation, severity, segments to investigate, and a data-quality vs business classification.
4. **Experiment readouts** that check validity (SRM, balance) before reporting a lift. They state both statistical and practical significance.
5. **Scenario simulation** in which every figure is labelled *observed / assumption / forecast / estimate*.
6. **A natural-language Q&A tool** constrained to governed metrics. It refuses ungoverned metrics and validates every number against the evidence.

## Non-functional requirements

| Requirement | Target | How it is met |
|---|---|---|
| Freshness | Daily batch. Alert if the last load is more than 26 h old | `raw._ingestion_audit`, dbt source freshness, DQ check T1 |
| Reproducibility | `make all` from a clean clone | Seeded generator, Docker, pinned packages, CI |
| Correctness | 0 error-severity dbt test failures | About 180 dbt tests; the build stops on errors |
| Transparency | Every known defect is visible | Warn-severity tests plus the DQ scorecard |
| Privacy | No raw PII in marts | Email hashed in staging. No names or phone numbers are collected |
| Performance | Dashboard queries return in under 2 s | BI reads pre-aggregated `metrics_*` and `mart_*` tables |

## Out of scope (deliberately)

Real-time streaming, inventory and supply chain, tax (GST) accounting, and multi-touch attribution. These are listed in the README as future work.
