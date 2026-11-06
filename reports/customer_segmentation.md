# Customer Segmentation (RFM)

Scored as of 2025-09-30, then **validated on Q4 2025 behaviour**, which the scoring never saw.

| segment | customers | avg_recency | avg_orders | total_cm | q4_active_rate | q4_cm_per_customer | share_of_cm | recommended_action |
|---|---|---|---|---|---|---|---|---|
| Champions | 1712 | 25.36 | 9.46 | 7.484e+06 | 0.6682 | 794 | 0.4012 | VIP perks, referrals; do NOT discount |
| Loyal | 1550 | 111.5 | 5.451 | 3.845e+06 | 0.2703 | 225.7 | 0.2061 | Cross-sell, membership offer |
| At Risk (was loyal) | 1577 | 372.4 | 5.157 | 3.748e+06 | 0.01205 | 8.016 | 0.2009 | Personal win-back (non-discount first), survey |
| Cannot Lose (big spend, lapsed) | 573 | 439.4 | 1.6 | 1.073e+06 | 0.01396 | 5.605 | 0.0575 | High-touch win-back, CX call |
| New / Promising | 2758 | 29.32 | 1.28 | 9.429e+05 | 0.3561 | 293.5 | 0.05055 | Onboarding journey, 2nd-order nudge within 30 days |
| Hibernating | 2764 | 439.2 | 1.26 | 8.198e+05 | 0.01773 | 10.49 | 0.04395 | Low-cost reactivation only; suppress paid retargeting |
| Needs Attention | 1352 | 147.6 | 1.344 | 7.427e+05 | 0.1546 | 101.1 | 0.03981 | Light-touch nurture |

* If the segmentation is useful, future activity should fall monotonically from Champions to Hibernating.
  The `q4_active_rate` column checks exactly that, out of sample.
* Contribution margin, not revenue, is the monetary input. A customer who only buys on 40% coupons and
  returns half of it should not rank as a "big spender".

> **Should conclude:** segments rank customers by the likelihood and value of future orders, and
> each one comes with a concrete CRM action. **Should NOT conclude:** that moving a customer into
> "Champions" *causes* higher value. Segments are descriptive. Test interventions per segment with holdouts.
