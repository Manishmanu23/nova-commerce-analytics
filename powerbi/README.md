# Power BI: build guide

## Two deliverables in this folder

| | What | Use it for |
|---|---|---|
| `dashboard/NovaCommerce_Dashboard.html` | A **working 6-page interactive dashboard** (Power BI layout, real governed data, period slicers, drill-downs, live simulator). Open it in any browser; the only external request is Chart.js from jsDelivr | GitHub/LinkedIn demo, interviews, and the blueprint you copy when building the `.pbix` |
| `data/*.csv` | **The Power BI data pack**: every dimension, fact, mart, metric and analytics table as CSV (from `make dashboard`) | Building the `.pbix` in Power BI Desktop **without** Docker/Postgres (Get data → Text/CSV) |
| `screenshots/` | PNGs of each dashboard page | README and portfolio |

Regenerate both after any pipeline run: `make dashboard` (or `python -m nova.dashboard.export`).

> **Why no `.pbix` in the repo?** A `.pbix` is a binary file that only Power BI Desktop (on Windows) can write. Build it yourself in about 2–3 hours with the steps below, then save it as `powerbi/NovaCommerce.pbix`. Building it yourself also means you can explain every relationship and measure in an interview.

## Option B: build from the CSV data pack (no database)

1. Power BI Desktop → **Get data → Text/CSV**. Load every file in `powerbi/data/`. In Power Query set types: dates → *Date*, flags → *True/False*, amounts → *Decimal*.
2. Create the relationships in section 3 below. The CSV table names match the database table names.
3. Add the measures from `dax_measures.md`, then build the pages from `report_spec.md`, using the HTML dashboard as the visual reference.

The `.pbix` is a binary file you build locally in Power BI Desktop (Windows, free) by following this guide. Everything the report needs is already modelled in the warehouse, so Power BI does **presentation and filter context only**. No business logic is re-implemented in DAX (see ADR-004).

Files here:

- `report_spec.md`: the 6 pages (purpose, audience, KPIs, visuals, filters, drill-downs, questions, actions)
- `dax_measures.md`: the full measure library
- `theme.json`: colour palette and typography
- `power_query.m`: parameterised connection

## Option A: connect to PostgreSQL

## 1. Connect

1. Start the database (`make db-up`) and run the pipeline (`make all`).
2. Power BI Desktop → **Get data → PostgreSQL database**. Server `localhost:5432`, database `nova`, **Import** mode. If you need the driver, install the Npgsql driver bundled with Power BI.
3. Alternatively, use `power_query.m` with the parameters `PgServer` and `PgDatabase`.

## 2. Tables to import (and nothing else)

| Table | Role |
|---|---|
| `marts.dim_date` | **Mark as date table** (`date_day`) |
| `marts.dim_customer` (filter `is_current = true` in Power Query for slicers) and `marts.dim_geography`, `dim_channel`, `dim_campaign`, `dim_product`, `dim_device`, `dim_payment_method` | Dimensions |
| `marts.fct_orders`, `marts.fct_order_items`, `marts.fct_payments`, `marts.fct_refunds`, `marts.fct_marketing_spend` | Facts |
| `marts.mart_funnel_daily`, `marts.mart_cohort_retention`, `marts.mart_channel_monthly_economics`, `marts.mart_customer_ltv` | Pre-aggregated marts |
| `metrics.metrics_daily`, `metrics.metrics_monthly`, `metrics.metric_catalog` | Governed metrics + definitions (tooltips) |
| `dq.dq_scorecard`, `dq.dq_checks`, `dq.dbt_test_results` | Data quality page |
| `analytics.anomaly_alerts`, `analytics.anomaly_segment_alerts`, `analytics.anomaly_segment_drilldown`, `analytics.anomaly_scores` | Anomaly centre |
| `analytics.scenario_baseline`, `analytics.scenario_summary`, `analytics.revenue_forecast`, `analytics.customer_segments` | Simulator, forecast, segments |

## 3. Relationships (star, single direction)

- `dim_date[date_day]` 1→* `fct_orders[order_date]`, `fct_order_items[order_date]`, `fct_payments[payment_date]`, `fct_marketing_spend[spend_date]`, `metrics_daily[date_day]`, `mart_funnel_daily[date_day]`
- `dim_customer[customer_version_key]` 1→* `fct_orders[customer_version_key]` (SCD2: as-of attributes)
- `dim_product[product_version_key]` 1→* `fct_order_items[product_version_key]`
- `dim_geography[geo_id]` 1→* `fct_orders[geo_id]`, `fct_payments[geo_id]`
- `dim_channel[channel]` 1→* `fct_orders[attributed_channel]`, `fct_marketing_spend[channel]`
- `dim_campaign[campaign_id]` 1→* `fct_orders[campaign_id]`, `fct_marketing_spend[campaign_id]`
- `fct_orders[order_id]` 1→* `fct_order_items[order_id]` (**single direction**). No bidirectional filters: they create ambiguous paths and slow the model.

## 4. Model hygiene

- Hide all FK and technical columns and the raw `_inr` columns. Expose **measures**, not columns, for numbers.
- Set `Summarize by = None` on every numeric column, so nobody can drag a column and get an unfiltered SUM.
- Display folders: `01 Revenue`, `02 Margin`, `03 Customers`, `04 Funnel`, `05 Marketing`, `06 Quality`, `07 Simulator`.
- Format currency in Indian style: `₹#,##,##0`. Use lakh/crore labels via the `Fmt ₹` measures.
- Put the definition from `metric_catalog` in every KPI card's tooltip.
- **RLS (optional):** role `Region` with `dim_geography[region] = USERPRINCIPALNAME()`-mapped regions via a mapping table.
- **Incremental refresh (production):** `RangeStart`/`RangeEnd` on `fct_orders[order_date]`. Refresh the last 30 days, which covers late refunds.

## 5. Screenshots

`screenshots/` currently holds the HTML dashboard pages. After you build the `.pbix`, replace them with Power BI exports (File → Export → PDF/PNG), keeping the same names.

## 6. Visual build checklist (page by page)

| Page | Build these visuals (Power BI visual type) |
|---|---|
| 1 Executive | 9 × Card (new card visual) · Line and clustered column chart (net revenue + CM %) · Waterfall (disconnected `Waterfall Steps` table) · Decomposition tree (Net Revenue by channel → customer_type → category) · Table of `anomaly_segment_alerts` + `anomaly_alerts` filtered to business/data_quality |
| 2 Customer | Cards · Matrix heatmap (rows cohort_month, columns months_since_first, values `Retention %`, conditional formatting background) · Line chart by acquisition_segment · Stacked column by customer_type · Table of `customer_segments` · Clustered column LTV vs CAC |
| 3 Product | Category slicer · Cards · Matrix (category: net, GM %, refund rate) · Line chart brand × quarter refund rate · Bar chart Top N (filter pane → Top 8 by Gross Profit) · Stacked bar refund reasons |
| 4 Marketing & Funnel | Cards · Table from `mart_channel_monthly_economics` · Scatter (CAC vs CM90, size = customers) · Funnel visual with `Funnel Steps` · Line chart app payment success by state, weekly · Line chart checkout conversion by device · Table `experiment_results` |
| 5 DQ & Anomaly | Cards (DQ score, verdict) · Bar chart `dq_scorecard` · Table `dq_checks` with status icons · Line chart daily net revenue + scatter of incidents · Table/cards of incidents |
| 6 Simulator | 7 What-if parameters (Modeling → New parameter) · Observed cards from `scenario_baseline` · Estimate cards (`Sim *` measures) · Column chart `scenario_summary` with error bars · Line chart `revenue_forecast` with P10–P90 band |

