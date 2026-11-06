# Power BI Report Specification (6 pages)

Design rules:

- At most 6 visuals per page, plus KPI cards.
- Every KPI card shows its value, the vs-comparison, and the catalogue definition in the tooltip.
- A global header with a date range slicer and the **DQ verdict badge** (`DQ Verdict`) on every page.
- Colours: blue = actual, grey = comparison, red = adverse, amber = provisional or estimate.

---

## Page 1: Executive Command Center

| | |
|---|---|
| **Purpose** | Answer in 30 seconds: is growth profitable, and what changed? |
| **Audience** | CEO, CFO, leadership |
| **KPIs** | Net Revenue (MoM %, YoY %), Contribution Margin & CM % (Δ pp YoY), CM after Marketing, Orders, AOV, New Customers, CAC |
| **Visuals** | (1) KPI strip, 8 cards. (2) Combo: monthly net revenue bars + CM % line. (3) Waterfall: gross → CM after marketing for the selected period. (4) "What moved?" decomposition tree on Net Revenue (channel → customer_type → category). (5) Top-3 active anomaly cards from `anomaly_alerts` / `anomaly_segment_alerts` |
| **Filters** | Date range, order channel, region |
| **Drill-downs** | Month → week → day. Decomposition tree to any dimension. Drill-through to the Customer / Product / Marketing pages |
| **DAX** | `Net Revenue`, `Net Revenue YoY %`, `CM %`, `CM % Δ pp YoY`, `CM after Marketing`, `Waterfall Value`, `Fmt ₹ Net Revenue` |
| **Business questions** | BR-01, BR-02: Did profit grow as fast as revenue? What was it driven by? |
| **Executive actions** | Rebalance growth vs margin targets, escalate an anomaly, request a deep-dive |

## Page 2: Customer Intelligence

| | |
|---|---|
| **Purpose** | Are we acquiring and keeping valuable customers? |
| **Audience** | CMO, CRM lead, CEO |
| **KPIs** | Active customers, New customers, Repeat rate 90d, Churn 90d, LTV 180d (CM), Member order share |
| **Visuals** | (1) Cohort retention heatmap (cohort month × months since first; `Retention %`). (2) Retention curves by acquisition segment (highlights deep-discount cohorts). (3) RFM segment matrix from `customer_segments` (customers, CM share, recommended action). (4) New vs returning revenue mix (100% stacked). (5) LTV 180d by acquisition channel (mature only) |
| **Filters** | Acquisition channel, deep-discount flag, city tier, cohort range |
| **Drill-downs** | Segment → customer list (IDs only, no PII) |
| **Business questions** | BR-03, BR-10: Which acquisition sources create loyal customers? Who is at risk? |
| **Executive actions** | Fund retention for "At Risk" and "Cannot Lose". Stop acquisition sources with low 90-day repeat |
| **Caveat banner** | "Legacy customers (signed up before 2024) are excluded from cohort metrics; cohorts younger than 90/180 days are not shown in LTV" |

## Page 3: Product & Profitability

| | |
|---|---|
| **Purpose** | Where do we make and lose money by category, brand and product? |
| **Audience** | CFO, category heads, CX |
| **KPIs** | Gross Profit, Gross margin %, Discount rate, Refund rate (with provisional flag), Units |
| **Visuals** | (1) Category × month matrix: net revenue, GM %, refund rate (conditional formatting). (2) Brand refund-rate trend (VoltEdge highlighted) with defective-line rate. (3) Top/bottom 10 products by gross profit (`RANKX`). (4) Scatter: discount rate vs gross margin by category. (5) Refund reasons stacked bar |
| **Filters** | Category, brand, channel, order month |
| **Drill-downs** | Category → subcategory → product. Refund reason → orders |
| **Business questions** | BR-02, BR-06: Which products drive margin? Is any supplier's quality deteriorating? |
| **Executive actions** | Supplier corrective action (VoltEdge), repricing, stop promoting low-margin SKUs |

## Page 4: Marketing & Funnel

| | |
|---|---|
| **Purpose** | Is spend buying profitable growth, and where does the funnel leak? |
| **Audience** | CMO, Head of Product, growth team |
| **KPIs** | Marketing spend, CAC, Blended CAC, ROAS, LTV:CAC, Conversion rate, Checkout conversion, Payment success |
| **Visuals** | (1) Channel economics table from `mart_channel_monthly_economics` (spend, new customers, CAC, 90d/180d LTV, LTV:CAC, CM after marketing). (2) Campaign scatter: CAC vs 90-day CM per customer (bubble = customers, payback line). (3) Funnel visual by `Funnel Steps` with a device slicer. (4) Checkout conversion and payment success by week × device (small multiples). (5) Payment success by state map for app users |
| **Filters** | Channel, campaign, device, app version, state |
| **Drill-downs** | Channel → campaign. Device → app version → state |
| **Business questions** | BR-03, BR-04: Which campaigns pay back? Is the app funnel healthy? |
| **Executive actions** | Cut deep-discount campaigns, reallocate budget to channels with LTV:CAC > 1.5, prioritise app payment fixes |

## Page 5: Data Quality & Anomaly Center

| | |
|---|---|
| **Purpose** | Can we trust today's numbers? What is unusual, and where? |
| **Audience** | Analytics, data engineering, and any executive before a decision |
| **KPIs** | DQ Score + verdict, open warnings, failing dbt tests, business-signal incidents, segment incidents, data freshness (hours) |
| **Visuals** | (1) DQ dimension bars (`dq_scorecard`). (2) Check table (`dq_checks`: observed vs thresholds, status, mitigation). (3) dbt test trend (warn/fail counts per run). (4) Anomaly timeline: metric × date with classification colour (business / DQ / seasonal / one-off). (5) Incident cards with expected, actual, deviation, severity, and **dimensions to investigate** (`anomaly_segment_drilldown`) |
| **Filters** | Metric, classification, severity, date |
| **Drill-downs** | Incident → segment drilldown → payments/sessions detail |
| **Business questions** | BR-07, BR-09 |
| **Executive actions** | Delay a decision when the verdict is "Not fit", assign an owner to an incident |
| **Honesty note** | Card subtitle: "Localises the change; does not establish the cause" |

## Page 6: Decision Simulator

| | |
|---|---|
| **Purpose** | Explore trade-offs before committing budget |
| **Audience** | CEO, CFO, CMO in planning |
| **Inputs (what-if)** | Retention Δpp, Conversion Δ%, AOV Δ%, CAC Δ%, Refund Δpp, Discount Δpp |
| **Visuals** | (1) **Observed** baseline card group (H2 2025 from `scenario_baseline`, grey). (2) **Assumption** slicers (amber panel). (3) **Estimate** cards: 12-month net revenue, CM, CM after marketing, end customers, LTV:CAC, each with Δ vs baseline. (4) Pre-computed scenario comparison from `scenario_summary`, with P10–P90 error bars. (5) Baseline **forecast** chart from `revenue_forecast` (P10–P90 band) |
| **Rules** | Every estimate visual shows the `Sim Label`. The forecast visual is titled "FORECAST". No simulated value appears on any other page |
| **Business questions** | BR-08: What if we cut discounts, improve retention, or fix the app funnel? |
| **Executive actions** | Pick scenarios to test (not to assume), and set targets with ranges instead of point values |
