# Statistical Analysis

## 1. Order value distribution (H2 2025, excluding B2B bulk orders)
| orders | mean | median | std | p90 | p99 | skewness | skew_of_log | mean_ci_low | mean_ci_high | median_ci_low | median_ci_high | mean_incl_bulk |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 21431 | 2,129 | 1,355 | 2,371 | 4,822 | 1.189e+04 | 3.379 | 0.02593 | 2,098 | 2,161 | 1,328 | 1,380 | 2,174 |

* Order value is strongly **right-skewed** (skewness 3.4; 0.0 on the log scale,
  so it is roughly log-normal). The mean sits well above the median.
* The 95% CI for the mean AOV is narrow (₹2,098 to ₹2,161) because n is
  large. Precision is not the problem, and the choice of statistic matters more: the median is ₹1,355.
  Including the 15 bulk orders moves the half-year mean from ₹2,129 to
  ₹2,174, which is small over six months. On a single day, though, one bulk order can move
  AOV by more than 50%, and that is why the governed AOV excludes them.

**App vs web order value.** Mann-Whitney p = 0.916, Cliff's δ = -0.001, and a Welch t-test on
log(value) gives p = 0.931. App median minus web median is roughly ₹+8.

> **Should conclude:** report AOV with the median alongside it and state the bulk-order rule. Any app/web
> difference is described by its *size* (δ), not just its p-value. |δ| < 0.15 is negligible even when p is tiny.
> **Should NOT conclude:** that app users "spend more *because* of the app". Channel choice is self-selected.

## 2. Refund rate by category, with Wilson 95% CIs (orders Jan–Nov 2025)
| category | lines | refunded | refund_line_rate | ci_low | ci_high |
|---|---|---|---|---|---|
| Beauty & Personal Care | 7869 | 338 | 0.04295 | 0.03869 | 0.04766 |
| Electronics | 8498 | 537 | 0.06319 | 0.05821 | 0.06856 |
| Fashion | 13083 | 1760 | 0.1345 | 0.1288 | 0.1405 |
| Grocery & Gourmet | 6642 | 107 | 0.01611 | 0.01335 | 0.01943 |
| Home & Kitchen | 7314 | 381 | 0.05209 | 0.04723 | 0.05742 |
| Sports & Fitness | 4847 | 276 | 0.05694 | 0.05076 | 0.06382 |
| Unknown | 89 | 6 | 0.06742 | 0.03126 | 0.1394 |

Chi-square test of independence (category × refunded): χ² = 1,269, dof = 6, p = 6.1e-271.

> **Should conclude:** categories differ in return propensity. Where two CIs do not overlap, the gap is not
> sampling noise. **Should NOT conclude:** that a category is "bad". Fashion's high rate is size-driven and
> structural. The actionable signal is a *change* within a brand (see sql/analysis/13, VoltEdge).
> December is excluded because refunds arrive late (right-censoring).

## 3. A sampling trap: right-censoring in repeat rate
| cohort_month | naive_repeat_rate | mature_only_repeat_rate |
|---|---|---|
| 2025-07-01 | 0.5731 | 0.5731 |
| 2025-08-01 | 0.4299 | 0.4299 |
| 2025-09-01 | 0.4427 | 0.4427 |
| 2025-10-01 | 0.4209 | 0.4158 |
| 2025-11-01 | 0.4291 |  |
| 2025-12-01 | 0.1963 |  |

The "naive" rate includes customers who have not yet had 90 days to repeat, so recent cohorts look
worse than they are. The governed metric (`repeat_purchase_rate_90d`) uses only mature cohorts. Blank
cells mean "not yet measurable", not zero.

> **Should NOT conclude** from a naive dashboard that "recent cohorts are much less loyal". Part of the drop
> is a measurement artefact. The true, planted part of the drop (the S1 discount cohort) only shows once
> those cohorts mature.

## 4. Mix vs rate: why overall conversion moved (Q2 → Q4 2025)
| device_type | share_Q2 | share_Q4 | conv_Q2 | conv_Q4 |
|---|---|---|---|---|
| desktop | 0.2325 | 0.2433 | 0.03162 | 0.03122 |
| mobile_app | 0.2895 | 0.2851 | 0.04354 | 0.04302 |
| mobile_web | 0.478 | 0.4716 | 0.02131 | 0.02154 |

Overall conversion went from 3.014% to 3.002% (-0.012%). Of that change, the **mix effect**
(a shift in device share) was +0.001% and the **rate effect** (conversion within each device) was -0.014%.

> **Should conclude:** before blaming the funnel, check whether the traffic mix changed. The two effects can
> point in opposite directions (Simpson's paradox). **Should NOT conclude** anything from the overall rate alone.
