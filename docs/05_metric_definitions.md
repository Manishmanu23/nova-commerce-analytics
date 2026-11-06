# Metric Governance: Certified Metric Definitions

**Owner of this document:** Analytics. **Sign-off:** Finance (revenue and margin metrics), Marketing (acquisition metrics), Product (funnel metrics).
**Single source of truth:** `dbt/nova_dbt/seeds/metric_catalog_seed.csv` → `metrics.metric_catalog`. The implementations live in `metrics.metrics_daily`, `metrics.metrics_monthly` and `metrics.metrics_daily_by_dimension`.
**Rule:** Power BI, the anomaly detector and the Analytics Copilot read these tables. None of them re-implement a metric. If a number is not in the catalogue, it is not a company metric.

## Global rules that apply to every metric

| Rule | Definition | Why |
|---|---|---|
| **Countable order** | `is_completed` (status ∈ delivered, shipped, processing) **AND** `is_reportable` (order date inside the reporting window, not an internal `@novacommerce.test` order) | Cancelled and payment-failed orders never generated revenue. Test and invalid-date orders are not real business. |
| **Time zone** | All dates are **IST**. Sources emit UTC, and staging converts them with `to_ist()`. | An order placed at 23:00 IST on 31 Oct is a *November* order in UTC. Mixing time zones shifts about 15% of evening orders across day boundaries. |
| **De-duplication** | The latest extract per `order_id` wins. Payments are de-duplicated on `gateway_txn_ref`. | OMS retries and webhook replays would double-count revenue and collections. |
| **Pre-filtered measures** | Governed columns in `fct_orders` / `fct_order_items` are **already 0** when the order is not countable. | `SUM(net_revenue)` is always correct. No analyst has to remember the filters. |
| **Ratios** | Stored as numerator + denominator. Re-aggregate as `SUM(num) / SUM(den)`. | Averaging daily ratios weights a quiet day the same as a peak day. |
| **Currency** | INR, GST-inclusive selling prices. Tax is not separated (see Limitations). | Matches what customers pay and what the OMS reports. |
| **Attribution** | Last non-direct touch: session UTM campaign → signup campaign (first orders only) → session channel → `direct`. Marketplace orders → `marketplace`. | Simple, explainable, reproducible. Its bias (it over-credits bottom-funnel channels) is documented. |
| **Maturity** | Cohort metrics count only customers with enough elapsed time. Refund-based metrics are provisional for the last 21 days. | Right-censoring would otherwise make recent periods look worse. |
| **Legacy customers** | Customers who signed up before 2024-01-01 are excluded from cohort, retention, LTV and repeat metrics, and included in revenue. | Their pre-2024 order history was not migrated, so we cannot know their true first order. |

---

## 1. Gross Revenue

| | |
|---|---|
| **Business definition** | Value of goods sold on countable orders, at the price the customer saw after product markdowns, before coupons and refunds. |
| **Formula** | Σ (quantity × unit_sale_price) over lines of countable orders |
| **Grain** | Order line, aggregated to any level |
| **Filters** | `is_countable` |
| **Exclusions** | Cancelled and payment-failed orders, test orders, invalid dates, shipping fees |
| **Owner** | Finance |

```sql
select order_date, sum(gross_revenue) as gross_revenue
from marts.fct_orders            -- governed column already 0 unless is_countable
group by 1;
```

**Edge cases.** B2B bulk orders are included, because they are real revenue. Orphan product lines are included, with the category shown as "Unknown". Late status changes (for example, an order cancelled after extraction) are picked up by the latest-extract-wins rule.

**Common mistakes**

- Summing `order_total_inr`, which includes shipping fees and is net of coupons. That is a different number.
- Using `unit_list_price`, which ignores markdowns, so revenue is overstated during sales.
- Forgetting to de-duplicate raw orders. The 2025-03-18 re-sent batch would double that day.

## 2. Net Revenue ★ (primary executive metric)

| | |
|---|---|
| **Business definition** | Revenue NovaCommerce keeps from goods sold: gross revenue minus coupon discounts minus processed return refunds. |
| **Formula** | Gross Revenue − Coupon Discounts − Processed Return Refunds |
| **Grain** | Order (line-level version is in `fct_order_items`, with coupons allocated pro rata) |
| **Filters** | `is_countable`. Refunds: `refund_status = 'processed'` and `NOT is_cancellation_refund` |
| **Exclusions** | Shipping fees (they sit in contribution margin), cancellation refunds, pending and rejected refunds |
| **Owner** | Finance |

```sql
select order_month, sum(net_revenue) as net_revenue
from marts.fct_orders group by 1;

-- equivalent explicit form (what the governed column encodes)
select o.order_month,
       sum(i.gross_revenue) - sum(i.allocated_coupon) - sum(i.return_refunds) as net_revenue
from marts.fct_order_items i join marts.fct_orders o using (order_id)
where o.is_countable
group by 1;
```

**Edge cases.** Refunds are attributed to the **order date**, not the refund date. This measures the quality of what was sold in a period, but it means a period's net revenue keeps falling for about 3 weeks as refunds arrive, so the dashboard shows it as *provisional*. A partial refund reduces revenue by the refunded amount. Negative-sign refunds from one source are corrected with `abs()` and flagged.

**Common mistakes**

- **Double-counting cancellations.** Subtracting cancellation refunds from gross revenue that never included the cancelled order.
- **Mixing bases.** Refunds by refund date combined with sales by order date. That gives a sales-quality view and a cash view blended together.
- **Using the raw layer.** It includes duplicates, test orders, paise amounts and 1970 dates.
- **Reconciliation.** The dbt test `sum_reconciles` checks that `metrics_daily`, `fct_orders` and `fct_order_items` agree. Two departments computing this differently is exactly what the catalogue prevents.

## 3. Gross Profit

| | |
|---|---|
| **Definition** | Net revenue minus the net cost of goods sold. |
| **Formula** | Net Revenue − (COGS − COGS recovered on restockable returns) |
| **Grain / filters** | Order line → order. `is_countable` |
| **COGS** | quantity × unit_cost of the **product version valid at order time** (SCD2) |
| **Recovered COGS** | Full return (≥ 99% of line value refunded) with reason ≠ `defective` → unit restocked, cost reversed |

```sql
select order_month, sum(gross_profit) as gross_profit,
       round(sum(gross_profit) / nullif(sum(net_revenue), 0), 4) as gross_margin_pct
from marts.fct_orders group by 1;
```

**Edge cases.** About 2% of product versions have no cost. For those, the cost is imputed from the category's median cost/price ratio and flagged `is_cost_imputed`. Orphan products use 60% of the list price, also flagged. Defective returns are written off, so their cost is not recovered.

**Common mistakes**

- Using today's product cost for last year's orders. The SCD2 join prevents this.
- Ignoring returns in COGS, which overstates the cost of returned-and-restocked goods.
- Computing margin % as the average of line margins.

## 4. Contribution Margin ★

| | |
|---|---|
| **Definition** | What each order contributes after all variable costs of fulfilling it, before marketing and fixed costs. |
| **Formula** | Gross Profit + Shipping Fees Collected − Shipping Cost − Payment Gateway Fees − Marketplace Commission |
| **Grain** | Order |
| **Filters** | `is_countable` |
| **Variant** | **CM after marketing** = CM − net marketing spend. It is valid only at date, channel or campaign grain, because spend cannot be assigned to individual orders. |

```sql
select order_month, sum(contribution_margin) as cm,
       round(sum(contribution_margin) / nullif(sum(net_revenue), 0), 4) as cm_pct
from marts.fct_orders group by 1;

select month, sum(contribution_margin_after_marketing) from metrics.metrics_monthly group by 1;
```

**Edge cases.** Marketplace orders carry a 15% commission and no shipping cost. COD orders carry a flat ₹35 collection fee. Payment fees on cancelled prepaid orders are not charged against CM (a known simplification).

**Common mistakes**

- Allocating marketing spend to orders by revenue share and calling the result "order profit". That is an arbitrary allocation.
- Computing CM % over gross revenue in one report and over net revenue in another. **CM % is always over net revenue.**
- Forgetting marketplace commission, which makes marketplace look like the most profitable channel.

## 5. AOV (Average Order Value)

| | |
|---|---|
| **Definition** | Typical value of a completed order after coupons, excluding B2B bulk orders. |
| **Formula** | Σ (gross revenue − coupon discount) / count of orders, for countable orders where `NOT is_bulk_order` |
| **Grain** | Order |
| **Exclusions** | Bulk orders (any line with quantity ≥ 20), non-countable orders |

```sql
select order_month, sum(aov_order_value) / nullif(sum(aov_orders), 0) as aov
from marts.fct_orders group by 1;
```

**Edge cases.** Order value is heavily right-skewed. Report the median alongside AOV (`sql/analysis/27_aov_distribution.sql`). One bulk order of ₹1.5 lakh can move a day's mean AOV by more than 50%.

**Common mistakes**

- `AVG(order_total_inr)` includes shipping, bulk orders and failed orders.
- Averaging daily AOVs to get a monthly AOV.
- Using an AOV numerator (net of coupons) that differs from the revenue definition in a decomposition, so the effects no longer sum.

## 6. Conversion Rate (session)

| | |
|---|---|
| **Definition** | Share of web and app sessions that end in a purchase. |
| **Formula** | Non-bot sessions with a `purchase` event / non-bot sessions |
| **Grain** | Session |
| **Exclusions** | Bot sessions (`is_bot`), marketplace (no session data) |
| **Variant** | **Checkout conversion** = purchase sessions / sessions that began checkout |

```sql
select session_date, sum(purchase_sessions)::numeric / nullif(sum(sessions), 0) as conversion_rate
from metrics.metrics_daily group by 1;
```

**Edge cases.** A retried payment in the same session counts as one purchase session. COD orders count as purchased when they are placed (the session ends with an order), even if they are later cancelled.

**Common mistakes**

- Orders / sessions. That includes marketplace orders, which have no sessions, and double-counts multi-order sessions.
- Including the 2025-05-22 bot spike, which halves desktop conversion that day.
- Averaging the conversion rates of segments (Simpson's paradox). Always recompute from components.

## 7. Customer Acquisition Cost (CAC)

| | |
|---|---|
| **Definition** | Average acquisition spend needed to win one new *paying* customer through paid channels. |
| **Formula** | Net acquisition spend (campaigns with objective = acquisition; credit notes netted) / new customers whose first order is attributed to a paid campaign |
| **Grain** | Month × channel (or campaign) |
| **Exclusions** | Email/CRM spend (retention), organic customers, legacy customers |
| **Variant** | **Blended CAC** = acquisition spend / *all* new customers. It flatters paid media, so use it only for company-level efficiency. |

```sql
select month, sum(acquisition_spend) / nullif(sum(paid_new_customers), 0) as cac
from metrics.metrics_monthly group by 1;
```

**Edge cases.** Spend and customers are matched by *month of first order*. Customers who sign up in month M and buy in M+1 create a small timing mismatch, which is acceptable at monthly grain and documented. Negative spend rows are platform credit notes and are netted, not dropped.

**Common mistakes**

- Counting sign-ups instead of first *orders*. That understates CAC.
- Including retention (email) spend.
- Comparing a cheap CAC without the LTV of the same cohort. The S1 "Blitz" campaign had the **lowest CAC (₹359) and the worst 90-day contribution per customer (₹212)**.

## 8. Customer Lifetime Value (LTV)

| | |
|---|---|
| **Definition** | Contribution margin a newly acquired customer generates in their first 180 days. |
| **Formula** | Σ contribution margin in [first order, first order + 180 days) / number of customers, for **mature** cohorts only (`is_mature_180d`) |
| **Grain** | Customer → cohort month × acquisition channel |
| **Exclusions** | Legacy customers, test customers, customers with less than 180 days of history |
| **Variants** | `cm_90d`, `cm_365d` (in `mart_customer_ltv`). The simulator uses a geometric LTV = CM per customer-month / monthly churn, labelled as an **estimate**. |

```sql
select first_order_channel, avg(cm_180d) as ltv_180d_cm, count(*) as customers
from marts.mart_customer_ltv
where is_mature_180d
group by 1;
```

**Assumptions that can make LTV wrong:** revenue-based instead of margin-based LTV, including immature customers, extrapolating one festive cohort, ignoring returns and discounts, assuming constant churn, and survivorship (measuring only customers who are still active).

**Common mistakes**

- `total revenue / total customers`. That has no time window and no margin, and mixes cohorts.
- Presenting a projected LTV as observed.

## 9. Retention (monthly cohort)

| | |
|---|---|
| **Definition** | Of the customers acquired in month M, the share who place at least one countable order in month M + N. |
| **Formula** | active customers (cohort, N) / cohort size |
| **Grain** | Cohort month × months since first order (× acquisition segment) |
| **Exclusions** | Legacy customers |

```sql
select cohort_month, months_since_first,
       sum(active_customers)::numeric / sum(cohort_size) as retention
from marts.mart_cohort_retention
group by 1, 2 order by 1, 2;
```

**Validation.** Month 0 must equal 100% (dbt test `assert_retention_month0_is_100pct`). `sql/analysis/05` rebuilds the matrix independently from `fct_orders`, and both must agree.

**Common mistakes**

- Defining the cohort by *signup* month, which dilutes it with non-buyers.
- Counting orders instead of distinct customers.
- Showing unobservable future cells as 0%.
- Averaging retention percentages across cohorts without weighting by cohort size.

## 10. Churn (90-day inactivity)

| | |
|---|---|
| **Definition** | Share of recently active customers who stop buying. Commerce has no cancel event, so churn must be *defined*. |
| **Formula** | At date D: active base = customers with ≥ 1 order in [D − 90, D). Churned = those with no order in [D, D + 90). Churn = churned / active base |
| **Grain** | Month start (as-of) |
| **Filters** | Only as-of dates with a complete 90-day forward window |

```sql
select month, churned_customers, active_base, churn_rate_90d
from metrics.metrics_monthly where churn_rate_90d is not null;
```

**Why 90 days:** about the 80th percentile of time between orders (`sql/analysis/06`). A shorter window mislabels slow repeat buyers as churned.

**Common mistakes**

- Computing churn for the last 3 months (the forward window is not complete, so churn looks huge).
- Using "no order this month" as churn.
- Using a membership cancellation as customer churn.

## 11. Repeat Purchase Rate (90-day)

| | |
|---|---|
| **Definition** | Share of new customers who place a second countable order within 90 days of their first. |
| **Formula** | new customers with `orders_90d ≥ 2` / new customers, for mature cohorts (`is_mature_90d`) |
| **Grain** | Acquisition (cohort) month |

```sql
select cohort_month, avg(repeated_within_90d::int) as repeat_rate_90d
from marts.mart_customer_ltv where is_mature_90d group by 1;
```

**Common mistakes.** Including immature customers. `reports/statistical_analysis.md §3` shows how badly this biases recent cohorts.

## 12. Refund Rate (value)

| | |
|---|---|
| **Definition** | Share of gross revenue that is returned and refunded. |
| **Formula** | Processed return refunds / gross revenue, by **order date** |
| **Grain** | Order line → any |
| **Exclusions** | Cancellation refunds, pending and rejected refunds |
| **Maturity** | Provisional for the last 21 days (`metrics_daily.is_refund_mature`) |
| **Variant** | Line-count refund rate (`refunded_lines / order_lines`) for quality analysis |

```sql
select month, sum(return_refunds) / nullif(sum(gross_revenue), 0) as refund_rate
from marts.mart_product_monthly group by 1;
```

**Common mistakes**

- Refund-date numerator over order-date denominator.
- Including cancellation refunds, which double-counts them.
- Reading last month's low refund rate as an improvement. It is late-arriving data (see `sql/analysis/23`).

## 13. ROAS (Return on Ad Spend)

| | |
|---|---|
| **Definition** | Net revenue attributed to paid campaigns per rupee of marketing spend. |
| **Formula** | Net revenue of orders with a paid `campaign_id` / net marketing spend |
| **Grain** | Date × campaign / channel |

```sql
select month, channel, roas from marts.mart_channel_monthly_economics order by 1, 2;
```

**Common mistakes**

- Gross-revenue ROAS (ignores returns and coupons).
- Treating ROAS as profitability. A 3x ROAS at a 20% CM is a loss.
- Comparing ROAS across attribution models.
- Forgetting that last-touch ROAS over-credits retargeting.

## 14. Revenue per Visitor (RPV)

| | |
|---|---|
| **Definition** | Net revenue from web and app orders per non-bot session. |
| **Formula** | Net revenue (order_channel ∈ web, app) / non-bot sessions |
| **Edge case** | There is no cross-device visitor ID, so **session is the visitor proxy**. RPV here is "revenue per session". This is named honestly in the catalogue. |

```sql
select date_day, web_app_net_revenue / nullif(sessions, 0) as revenue_per_visitor from metrics.metrics_daily;
```

**Common mistake.** Dividing all revenue (including marketplace) by web sessions.

## 15. Payment Success Rate

| | |
|---|---|
| **Definition** | Share of prepaid payment attempts that succeed. |
| **Formula** | Successful prepaid attempts / prepaid attempts (COD excluded) |
| **Grain** | Payment attempt |

```sql
select payment_date, avg(is_success::int) from marts.fct_payments
where is_prepaid_attempt and is_reportable group by 1;
```

**Common mistakes**

- Order-level success (hides retries).
- Counting webhook replays twice.
- Reading only the national number. The S2 UPI failure moved the national rate a little, but app payment success in Uttar Pradesh went from 91.5% to 54.4%.

---

## Change control

1. **Proposing a change.** Open a PR that edits the seed row and the dbt model. Update this document. Add or adjust the reconciliation tests.
2. **Approval.** Finance approves revenue and margin metrics. Marketing approves acquisition metrics. Product approves funnel metrics.
3. **Definition changes.** Any change to a definition bumps the catalogue `definition` text and is announced with a before/after reconciliation of the last 12 months.
4. **Conflicting definitions.** When two departments define a metric differently (for example, Marketing's "revenue" = gross), **both** can exist, but under **different names** (`gross_revenue` vs `net_revenue`). Only the certified one appears on executive pages.
