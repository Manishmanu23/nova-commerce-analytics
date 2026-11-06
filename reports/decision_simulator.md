# Decision Simulator: example scenarios (12 months ahead)

## Observed baseline parameters (H2 2025, from governed metrics). Label: OBSERVED
| parameter | value |
|---|---|
| base_customers | 5,522 |
| churn_m | 0.1997 |
| orders_per_customer | 0.6473 |
| aov_gross | 2,260 |
| discount_rate | 0.03149 |
| refund_rate | 0.06411 |
| cogs_pct | 0.667 |
| variable_cost_per_order | 151.6 |
| marketing_spend | 3.966e+05 |
| acq_spend | 3.824e+05 |
| cac | 531.7 |
| organic_new | 232 |

## Scenario assumptions. Label: ASSUMPTION (set by a human, not measured)
| name | retention_pp | conversion_pct | aov_pct | cac_pct | refund_pp | discount_pp | marketing_pct |
|---|---|---|---|---|---|---|---|
| baseline | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Fix app payments (+3% conversion) | 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| Stop deep-discount acquisition | 0 | -1 | 0 | 15 | -0.5 | -1.5 | 0 |
| Retention programme (-1pp monthly churn, +10% marketing) | 1 | 0 | 0 | 0 | 0 | 0 | 10 |
| Price +3% (assume -2% conversion) | 0 | -2 | 3 | 0 | 0 | 0 | 0 |

## Results. Labels: baseline = FORECAST, scenarios = ESTIMATE
| scenario | value_type | net_revenue_12m | cm_12m | cm_after_mkt_12m | end_customers | ltv_cm | ltv_to_cac | delta_cm_after_mkt_vs_base | cm_after_mkt_p10 | cm_after_mkt_p90 |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | forecast | 8.031e+07 | 1.513e+07 | 1.037e+07 | 4,828 | 1,248 | 2.347 | 0 | 4.829e+06 | 1.653e+07 |
| Fix app payments (+3% conversion) | estimate | 8.307e+07 | 1.564e+07 | 1.088e+07 | 4,860 | 1,285 | 2.417 | 5.194e+05 | 5.159e+06 | 1.726e+07 |
| Stop deep-discount acquisition | estimate | 7.653e+07 | 1.576e+07 | 1.1e+07 | 4,388 | 1,380 | 2.257 | 6.332e+05 | 5.261e+06 | 1.697e+07 |
| Retention programme (-1pp monthly churn, +10% marketing) | estimate | 8.646e+07 | 1.628e+07 | 1.105e+07 | 5,405 | 1,314 | 2.47 | 6.824e+05 | 5.076e+06 | 1.769e+07 |
| Price +3% (assume -2% conversion) | estimate | 8.084e+07 | 1.54e+07 | 1.064e+07 | 4,807 | 1,274 | 2.396 | 2.738e+05 | 5.011e+06 | 1.689e+07 |

P10/P90 come from 300 Monte-Carlo draws of the observed month-to-month variability of the inputs. They
capture parameter noise, **not** model error. The true uncertainty is wider.

### How to read this
* The ranking of scenarios by `delta_cm_after_mkt_vs_base` is the output. The absolute rupee values are
  only as good as the assumptions.
* "Stop deep-discount acquisition" only helps under the stated assumption about lost conversion. Change
  that assumption, and the answer can flip. Say this out loud in the meeting.
* None of these numbers are results. Report them as "if X, we estimate Y".
