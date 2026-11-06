# Executive Memo: Profitable Growth Review (FY2025 H2)

**To:** CEO, CFO, CMO, Head of Product. **From:** Analytics. **Data:** governed metrics through 31 Dec 2025, DQ score 86.2 ("fit with caveats").
*All figures come from NovaCommerce's synthetic dataset and are **simulated**. Where a figure is estimated or forecast, it says so.*

## Bottom line

Revenue is growing fast, but the Aug–Oct 2025 growth was **bought with discounts that did not create loyal customers**. Contribution margin % dropped by about 7 points during that campaign, the cohorts it acquired repeat much less, and an app release in November quietly cost orders in three states. Our recommendations: **stop deep first-order discounts, make payment monitoring segment-level, fix VoltEdge quality with the supplier, and test membership causally before scaling it.**

## What happened

1. **Growth is strong.** Net revenue was ₹7.13 Cr in 2025 vs ₹4.19 Cr in 2024 (+70%). December rose 15.7% MoM and 72% YoY.
2. **Profitability diluted in H2.** CM % was 23.6% in H1 2025, fell to **16.5% in Aug–Oct**, and recovered to 20.8% in Nov–Dec. Coupon discounts rose from 1.5% to 4.9% of gross revenue. CM after marketing fell from 19.3% to 9.6% of net revenue.
3. **The driver was one campaign.** The Meta "Social Blitz" (40% off first order) had the **lowest CAC of any campaign (₹359)**, but its customers generated only **₹212 of contribution in 90 days** and **32% of them repeated**, against 45–55% for other cohorts. 90-day repeat rates for Aug–Oct cohorts fell to 42–44%, from 55–57% for Jun–Jul cohorts.
4. **An app release cost orders, and the national dashboard didn't show it.** From 12 Nov to 3 Dec (app v5.2.0), the national payment success rate barely moved. The segment monitor found **app payment success down 13.7%**, concentrated in Uttar Pradesh (91.5% → 54.4%), West Bengal and Bihar, and almost entirely on UPI. The app-UPI order failure rate went from 4.6% to 19.9%, roughly 64 extra failed orders in 3 weeks (≈₹1.5 lakh of order value at risk, simulated). The hotfix restored it.
5. **A quality risk is emerging.** VoltEdge (Electronics) refund rate climbed through 2025: about 3% early in the year, 14% in Q3 and 18% in Q4. Its defective-line rate went from 9% to 16%. Q4 is still provisional because refunds arrive late, so the true figure is likely higher.

## What we tested

- **One-page checkout:** +9.5% purchase rate (95% CI +1.0% to +18.8%). The effect is real, but its size is uncertain. **Ship with a 10% holdout.**
- **Free-shipping threshold ₹299:** the headline showed +28%, but the **sample ratio was broken** (1,808 vs 2,204 users, p = 4×10⁻¹⁰). The result is **invalid**. Fix the logging and re-run.
- **Homepage recommendations:** inconclusive. The test was underpowered (13% power), so it needs about 19k users per arm or a more sensitive metric.
- **Nova Plus membership:** "members order 4× more" is mostly selection. Comparing like with like shrinks the effect to about **+51% (an upper bound)**. A randomised free-trial test is needed before we spend on membership acquisition.

## Recommendations (with the simulator's estimates, 12 months, **ESTIMATES**)

| # | Action | Owner | Estimated Δ CM after marketing | Key assumption |
|---|---|---|---|---|
| 1 | Retention programme targeting "At Risk" and "New/Promising" RFM segments | CRM | +₹6.8 L | −1 pp monthly churn for +10% spend |
| 2 | Cap first-order discounts at 10–15%, and judge campaigns on 90-day CM payback instead of CAC | CMO | +₹6.3 L | CAC +15%, conversion −1% |
| 3 | Segment-level payment monitoring + release canary by state/PSP | Product/Eng | +₹5.2 L | +3% effective conversion |
| 4 | VoltEdge supplier corrective action. Pause promotion of its SKUs | Category | not modelled | — |
| 5 | Randomised Nova Plus trial (encouragement design) | Growth | decision value | — |

## Caveats

- The data is synthetic. Attribution is last-touch. Recent refunds are provisional. The simulator has no demand elasticity, so each scenario states its conversion assumption explicitly.
- Segment concentration tells us *where* a problem is. The causes above were confirmed by release notes and experiment design, not by the dashboards alone.
