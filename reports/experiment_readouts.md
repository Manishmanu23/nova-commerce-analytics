# Experiment Readouts

Pre-registered practical threshold (MDE): **+5% relative purchase rate**. α = 0.05. SRM alarm at p < 0.001. Unit = customer. Outcomes are counted only after assignment and before the experiment ends.

## EXP-2025-01: `one_page_checkout`

**Decision: SHIP WITH MONITORING (effect real, size uncertain)**. The lift is significant, but the CI (+1.0% to +18.8% relative) includes values below the +5% practical threshold. Ship only if rollout cost is low, and keep a 10% holdout to confirm the size.

| Check | Result |
|---|---|
| Sample sizes (T / C) | 1,793 / 1,835 |
| SRM chi-square p | 4.86e-01 |
| Pre-period balance (SMD of prior orders) | -0.049 (|SMD| < 0.1 = balanced) |
| Purchase rate C → T | 37.38% → 40.94% |
| Absolute lift (95% CI) | +3.55% (+0.38% to +6.72%) |
| Relative lift (95% CI) | +9.5% (+1.0% to +18.8%) |
| p-value (two-proportion z) | 0.0284 |
| Power to detect +5% | 21% (need ≈ 10,618 per arm for 80%) |
| Net revenue / user diff (Welch p; bootstrap 95% CI) | ₹+92.8 (p = 0.391; ₹-131.8 to ₹+309.6) |
| CUPED-adjusted revenue diff (variance reduction) | ₹+93.6 (p = 0.386; 0% variance removed) |
| Guardrail: CM / user diff | ₹+18.6 (p = 0.557) |
| Guardrail: shipping-fee revenue / user diff | ₹+0.13 (p = 0.705) |

**Secondary metrics & subgroups (multiple-testing corrected):**

| test | diff | p_raw | p_holm | p_bh | significant_raw | significant_holm |
|---|---|---|---|---|---|---|
| metric:converted | 0.03553 | 0.0284 | 0.2272 | 0.1278 | True | False |
| metric:orders_in_window | 0.09504 | 0.003615 | 0.03253 | 0.03253 | True | True |
| metric:net_revenue | 92.78 | 0.3914 | 1 | 0.5871 | False | False |
| metric:contribution_margin | 18.64 | 0.5566 | 1 | 0.7156 | False | False |
| metric:shipping_fee_paid | 0.1289 | 0.7048 | 1 | 0.7929 | False | False |
| subgroup:android conversion | -5.396e-05 | 0.9984 | 1 | 0.9984 | False | False |
| subgroup:desktop conversion | 0.03809 | 0.2543 | 1 | 0.4577 | False | False |
| subgroup:ios conversion | 0.08828 | 0.1048 | 0.6287 | 0.2358 | False | False |
| subgroup:mobile_web conversion | 0.05571 | 0.05021 | 0.3515 | 0.1506 | False | False |


> **Should conclude:** the change very likely increases purchase rate. The CI gives the plausible size, and the holdout will pin it down. **Should NOT conclude:** that the point estimate is the exact size, or that revenue will rise by the same %. Revenue is noisier; check its CI separately.

## EXP-2025-02: `free_shipping_threshold_299`

**Decision: INVALID: sample ratio mismatch**. Observed split 1808/2204 vs planned 50% (chi-square p = 4.1e-10). Randomisation or exposure logging is broken, so the arms are not comparable and **no lift estimate from this test should be used**. Next step: compare assignment logs with exposure logs by platform and day, fix the logging, and re-run.

| Check | Result |
|---|---|
| Sample sizes (T / C) | 1,808 / 2,204 |
| SRM chi-square p | 4.05e-10 |
| Pre-period balance (SMD of prior orders) | +0.013 (|SMD| < 0.1 = balanced) |
| Purchase rate C → T | 29.22% → 37.50% |
| Absolute lift (95% CI) | +8.28% (+5.35% to +11.20%) |
| Relative lift (95% CI) | +28.3% (+17.5% to +40.2%) |
| p-value (two-proportion z) | 0.0000 |
| Power to detect +5% | 17% (need ≈ 15,428 per arm for 80%) |
| Net revenue / user diff (Welch p; bootstrap 95% CI) | ₹+346.9 (p = 0.000; ₹+206.2 to ₹+486.2) |
| CUPED-adjusted revenue diff (variance reduction) | ₹+346.7 (p = 0.000; 1% variance removed) |
| Guardrail: CM / user diff | ₹+23.9 (p = 0.236) |
| Guardrail: shipping-fee revenue / user diff | ₹-0.75 (p = 0.001) |

**Secondary metrics & subgroups (multiple-testing corrected):**

| test | diff | p_raw | p_holm | p_bh | significant_raw | significant_holm |
|---|---|---|---|---|---|---|
| metric:converted | 0.0828 | 3.274e-08 | 2.947e-07 | 2.947e-07 | True | True |
| metric:orders_in_window | 0.1001 | 8.66e-05 | 0.0006062 | 0.0002598 | True | True |
| metric:net_revenue | 346.9 | 1.604e-06 | 1.283e-05 | 7.22e-06 | True | True |
| metric:contribution_margin | 23.93 | 0.2356 | 0.3939 | 0.2356 | False | False |
| metric:shipping_fee_paid | -0.7529 | 0.001065 | 0.004258 | 0.001597 | True | True |
| subgroup:android conversion | 0.08867 | 0.0003663 | 0.002198 | 0.0007727 | True | True |
| subgroup:desktop conversion | 0.1123 | 0.0004293 | 0.002198 | 0.0007727 | True | True |
| subgroup:ios conversion | 0.06214 | 0.197 | 0.3939 | 0.2216 | False | False |
| subgroup:mobile_web conversion | 0.06325 | 0.01533 | 0.04598 | 0.01971 | True | True |


> **What a stakeholder should conclude:** nothing about the treatment. The comparison is biased. **Should NOT conclude:** "the lift was positive, so let's ship anyway". SRM usually means the users *missing* from one arm are systematically different (here: treatment users who never purchased were less likely to be logged), and that inflates the apparent lift.

## EXP-2025-03: `homepage_reco_widget`

**Decision: INCONCLUSIVE (underpowered)**. Power to detect +5% was only 13%. 'Not significant' here does **not** mean 'no effect'. About 19,085 users per arm would be needed.

| Check | Result |
|---|---|
| Sample sizes (T / C) | 1,680 / 1,712 |
| SRM chi-square p | 5.83e-01 |
| Pre-period balance (SMD of prior orders) | -0.020 (|SMD| < 0.1 = balanced) |
| Purchase rate C → T | 25.06% → 26.25% |
| Absolute lift (95% CI) | +1.19% (-1.75% to +4.13%) |
| Relative lift (95% CI) | +4.8% (-6.6% to +17.5%) |
| p-value (two-proportion z) | 0.4269 |
| Power to detect +5% | 13% (need ≈ 19,085 per arm for 80%) |
| Net revenue / user diff (Welch p; bootstrap 95% CI) | ₹-55.2 (p = 0.415; ₹-187.2 to ₹+78.4) |
| CUPED-adjusted revenue diff (variance reduction) | ₹-57.8 (p = 0.391; 1% variance removed) |
| Guardrail: CM / user diff | ₹+2.2 (p = 0.896) |
| Guardrail: shipping-fee revenue / user diff | ₹+0.14 (p = 0.611) |

**Secondary metrics & subgroups (multiple-testing corrected):**

| test | diff | p_raw | p_holm | p_bh | significant_raw | significant_holm |
|---|---|---|---|---|---|---|
| metric:converted | 0.01192 | 0.4271 | 1 | 0.7687 | False | False |
| metric:orders_in_window | 0.01301 | 0.58 | 1 | 0.7862 | False | False |
| metric:net_revenue | -55.23 | 0.4151 | 1 | 0.7687 | False | False |
| metric:contribution_margin | 2.197 | 0.8962 | 1 | 0.8962 | False | False |
| metric:shipping_fee_paid | 0.1379 | 0.6115 | 1 | 0.7862 | False | False |
| subgroup:android conversion | -0.02112 | 0.412 | 1 | 0.7687 | False | False |
| subgroup:desktop conversion | 0.02488 | 0.4193 | 1 | 0.7687 | False | False |
| subgroup:ios conversion | -0.008887 | 0.8641 | 1 | 0.8962 | False | False |
| subgroup:mobile_web conversion | 0.04451 | 0.08249 | 0.7424 | 0.7424 | False | False |


> **Should conclude:** the test could not distinguish a useful effect from zero. **Should NOT conclude:** "it doesn't work". Absence of evidence is not evidence of absence when power is low.

---
### Why these methods
* **SRM first**: if the split is wrong, every downstream number is biased. It is a free, decisive check.
* **Newcombe CI** behaves better than the simple Wald interval for proportions near 0/1 and for small n.
* **Welch t-test** does not assume equal variances. Revenue per user is heavily skewed (many zeros), so a
  **bootstrap CI** is reported alongside it.
* **CUPED** subtracts the part of the outcome that pre-period behaviour predicts. The estimate stays
  unbiased (the pre-period is independent of assignment) and its variance is lower, which shortens
  the test.
* **Holm / BH**: testing 9 things at α=0.05 gives about a 37% chance of at least one false positive.
  Holm controls that family-wise error, and BH controls the false-discovery rate (less conservative).
* **Practical significance**: a lift can be statistically real and still too small to pay for itself.
  The MDE is agreed *before* the test.
