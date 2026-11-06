# Causal question: does Nova Plus membership increase ordering?

Sample: 2,624 members and 2,813 non-members with a full 90-day follow-up after their index date.
Coarsened matching found comparable non-members for only 17% of members. Poor overlap is itself a
finding: members are very different customers *before* they join.

| method | effect_orders_per_90d | counterfactual_baseline | relative_effect |
|---|---|---|---|
| 1 naive | 1.792 | 0.4081 | 4.39 |
| 2 regression adjusted | 1.598 | 0.4081 | 3.915 |
| 3 coarsened exact matching (ATT) | 1.389 | 0.6459 | 2.151 |
| 4 diff-in-diff on matched strata | 0.6929 | 1.35 | 0.5133 |

Regression 95% CI for the member coefficient: 1.482 to 1.714 orders per 90 days.

**Ground truth (simulation only, never available in real life):** membership raises the order rate by 15% while active and extends lifetime by 25%. The join probability rises steeply with latent loyalty (strong selection). Methods 2-4 move toward the truth but stay above it, which is expected because loyalty is only partly observable.

## Interpretation for leadership
* **Should conclude:** the raw "members order much more" statistic mostly reflects *who* joins. Once we
  compare against customers with the same history, the gap shrinks substantially.
* **Should NOT conclude:** "every new member will order X% more". The adjusted numbers are still likely an
  **upper bound**, because we cannot observe everything that makes a customer both join and order.
* **Recommended next step:** a randomised *encouragement* test. Offer a free first month to a random 50% of
  eligible customers, and estimate the effect of membership for those who take it up (instrumental
  variable / complier average causal effect). Only randomisation removes unobserved selection.

## Why correlation isn't enough here
Membership is chosen by the customer, and the same loyalty that drives joining also drives ordering.
Any metric that compares "members vs non-members" answers the question "are members different?"
(yes). It does not answer "does membership make them different?", which is the question leadership
is actually asking.
