# Data Quality Scorecard

Generated: 2026-11-02 19:23 UTC. **Overall score: 86.2 / 100 (fit with caveats (see warnings))**

Scores are threshold-based: each check has an explicit warn and fail tolerance, and a business impact.
Warnings are **known, monitored source defects**. The pipeline corrects or flags every one of them, and they
must never be silently ignored.

## Dimension scores
| dimension | checks | fails | warns | score | weight |
|---|---|---|---|---|---|
| Completeness | 3 | 0 | 3 | 80 | 0.8 |
| Consistency | 3 | 0 | 0 | 100 | 1.2 |
| Referential integrity | 2 | 0 | 2 | 80 | 1 |
| Timeliness | 2 | 0 | 1 | 90 | 0.8 |
| Uniqueness | 3 | 0 | 3 | 80 | 1 |
| Validity | 5 | 0 | 4 | 84 | 1 |
| OVERALL | 18 | 0 | 13 | 86.2 |  |

## Checks
| check_id | dimension | table_name | description | observed | warn_threshold | fail_threshold | status | mitigation |
|---|---|---|---|---|---|---|---|---|
| U1 | Uniqueness | orders | Raw order rows that are duplicates of an order_id | 0.0130 | 0.0050 | 0.0300 | warn | stg_orders keeps latest extract per order_id |
| U2 | Uniqueness | payments | Payment rows that replay an existing gateway_txn_ref | 0.0030 | 0.0010 | 0.0100 | warn | stg_payments de-dups on gateway_txn_ref |
| U3 | Uniqueness | customers | Exact-duplicate customer CDC rows | 0.0196 | 0.0100 | 0.0500 | warn | stg_customers de-dups exact CDC rows |
| C1 | Completeness | customers | Customers with no geography | 0.0404 | 0.0300 | 0.0800 | warn | mapped to 'Unknown' geography member |
| C2 | Completeness | products | Product versions with missing unit cost (imputed) | 0.0267 | 0.0100 | 0.0500 | warn | imputed from category median cost ratio; flagged is_cost_imputed |
| C3 | Completeness | marketing_spend | Spend rows with null impressions | 0.0098 | 0.0050 | 0.0500 | warn | CTR computed only where impressions present |
| V1 | Validity | orders | Orders with order date outside the reporting window | 0.0020 | 0.0010 | 0.0100 | warn | excluded via is_reportable |
| V2 | Validity | orders | Delivered before ordered | 0.0024 | 0.0010 | 0.0100 | warn | days_to_deliver set NULL; order kept |
| V3 | Validity | refunds | Refunds with negative sign (sign-corrected) | 0.0093 | 0.0050 | 0.0300 | warn | abs() applied in staging; flagged |
| V4 | Validity | products/customers | Raw category/channel labels needing a mapping | 0.0490 | 0.1000 | 0.4000 | pass | seed mapping tables |
| V5 | Validity | web_sessions | Share of sessions flagged as bots | 0.0118 | 0.0100 | 0.0500 | warn | is_bot flag; excluded from governed conversion |
| R1 | Referential integrity | order_items | Order lines whose product_id is not in the product master | 0.0020 | 0.0010 | 0.0100 | warn | 'unknown' product member; cost imputed |
| R2 | Referential integrity | orders | Orders whose customer is missing from the CRM extract | 0.0022 | 0.0020 | 0.0200 | warn | 'unknown' customer member; revenue kept |
| T1 | Timeliness | all | Hours since last successful load | 0.1701 | 26.0000 | 50.0000 | pass | freshness alert |
| T2 | Timeliness | refunds | Share of return refunds that arrived > 7 days after the event | 0.2972 | 0.2000 | 0.4000 | warn | metrics_daily.is_refund_mature flag |
| K1 | Consistency | payments vs orders | Completed prepaid orders where collected != order total | 0.0000 | 0.0010 | 0.0100 | pass | paise->INR conversion in stg_payments |
| K2 | Consistency | metrics | Governed net revenue: metrics_daily vs fct_orders (abs diff INR) | 0.0000 | 1.0000 | 100.0000 | pass | dbt sum_reconciles test |
| D1 | Consistency | dbt | dbt tests failing (error severity) - 125 tests, 8 known-defect warnings | 0.0000 | 1.0000 | 1.0000 | pass | build stops on error-severity tests |

## How to read this
* **pass**: within tolerance. **warn**: a known defect that is handled (de-duplicated, imputed, flagged).
  It is shown so that nobody is surprised. **fail**: a decision based on this data should wait.
* The score is not a KPI to maximise. It exists to answer "can leadership trust today's numbers?"
