# Anomaly Detection Report

**Level 1: top-line governed metrics.** Same-weekday robust z (median over 8 weeks, sale days masked out of
the baseline, empirical noise scale), an STL residual cross-check, and a quasi-binomial z for rates.
The thresholds are |z| ≥ 4.0 **and** |deviation| ≥ 10%. Both conditions must hold, because
statistical significance without business size is noise.
**Level 2: weekly segment scan for ratio metrics.** Every dimension value with at least 100
weekly attempts is checked, with thresholds z ≤ −4.0 and deviation ≤ −10%.

## Level-1 incident summary
| metric | business_signal | data_quality | expected_seasonal | one_off_outlier |
|---|---|---|---|---|
| net_revenue | 1 | 0 | 4 | 4 |
| orders | 1 | 0 | 6 | 0 |
| sessions_incl_bots | 1 | 1 | 5 | 0 |

## Top Level-1 incidents (excluding expected festive peaks)

**Metric:** Net Revenue  
**Window:** 2024-08-21 → 2024-08-21  
**Expected:** ₹84,795  
**Actual:** ₹170,792  
**Deviation:** +101.4% (max robust |z| 4.3; STL confirms: False)  
**Severity:** High  
**Classification:** business_signal: no data-quality marker on these dates  
**Potential dimensions to investigate** (largest contribution to the deviation):
- channel = **paid_search** (53% of the deviation)
- device_type = **desktop** (77% of the deviation)
- state = **Maharashtra** (36% of the deviation)
- customer_type = **returning** (88% of the deviation)
- category = **Electronics** (53% of the deviation)

---

**Metric:** Sessions (incl. bots)  
**Window:** 2025-05-22 → 2025-05-22  
**Expected:** 2,264  
**Actual:** 22,114  
**Deviation:** +876.8% (max robust |z| 67.9; STL confirms: True)  
**Severity:** High  
**Classification:** data_quality: bot sessions = 90% of traffic (flagged is_bot, excluded from governed conversion)  

---

**Metric:** Sessions (incl. bots)  
**Window:** 2025-03-22 → 2025-03-22  
**Expected:** 1,993  
**Actual:** 3,123  
**Deviation:** +56.7% (max robust |z| 4.7; STL confirms: True)  
**Severity:** High  
**Classification:** business_signal: no data-quality marker on these dates  

---

**Metric:** Completed Orders  
**Window:** 2024-03-30 → 2024-03-30  
**Expected:** 49  
**Actual:** 69  
**Deviation:** +40.8% (max robust |z| 4.1; STL confirms: False)  
**Severity:** High  
**Classification:** business_signal: no data-quality marker on these dates  
**Potential dimensions to investigate** (largest contribution to the deviation):
- channel = **direct** (38% of the deviation)
- device_type = **mobile_app** (37% of the deviation)
- state = **Telangana** (28% of the deviation)
- customer_type = **returning** (103% of the deviation)

---


## Level-2 segment incidents (most severe first)

**Metric:** Checkout Conversion, segment traffic_channel = **paid_social**  
**Window:** 2025-11-03 → 2025-11-30 (4 wk)  
**Expected:** 24.3%  
**Actual:** 13.8%  
**Deviation:** -43.3% (volume 1,934, |z| 6.7)  
**Severity:** High  
**Potential dimensions to investigate** (inside this segment; share of the deviation):
- state: Uttar Pradesh (15%; 33.8% → 9.8%), Maharashtra (13%; 26.9% → 15.8%), Tamil Nadu (9%; 27.1% → 11.5%)
- app_version: n/a (60%; 25.7% → 13.2%), 5.1.2 (16%; 32.3% → 18.5%)
- browser: NovaApp (43%; 32.3% → 14.8%), chrome (40%; 26.4% → 13.0%), safari (8%; 23.4% → 13.1%)
- device_type: mobile_app (43%; 32.3% → 14.8%), mobile_web (36%; 26.0% → 12.5%), desktop (21%; 25.4% → 14.1%)
*This localises the drop. It does not prove the cause.*

---

**Metric:** Payment Success, segment device_type = **mobile_app**  
**Window:** 2025-11-10 → 2025-11-30 (3 wk)  
**Expected:** 89.1%  
**Actual:** 76.9%  
**Deviation:** -13.7% (volume 754, |z| 7.8)  
**Severity:** High  
**Potential dimensions to investigate** (inside this segment; share of the deviation):
- state: Uttar Pradesh (24%; 91.5% → 54.4%), West Bengal (15%; 91.4% → 54.9%), Bihar (9%; 89.7% → 48.1%)
- payment_method: UPI (104%; 93.1% → 66.8%), Card (-3%; 91.4% → 93.2%), Wallet (-1%; 94.2% → 96.9%)
- app_version: 5.1.2 (15%; 92.8% → 81.0%)
*This localises the drop. It does not prove the cause.*

---


## Raw-layer scan (issues the governed layer has already neutralised)
| date_day | actual | expected | dup_rate |
|---|---|---|---|
| 2025-03-18 00:00:00 | 143 | 72 | 0.9861 |

## Evaluation against the planted ground truth
| planted event | when | detected / true | note |
|---|---|---|---|
| S2 UPI failures in 3 states (segment scan) | 2025-11-12..2025-12-03 | True | mobile_app |
| S2 visible in NATIONAL payment success? | 2025-11-12..2025-12-03 | False | averages hide segment problems |
| Bot spike -> sessions, classified data_quality | 2025-05-22 | True |  |
| S4 re-sent batch caught in RAW layer | 2025-03-18 | True |  |
| S4 absent from governed net revenue | 2025-03-18 | True | de-dup in staging works |

* Top-line incidents classified `business_signal`: **3**. Segment incidents outside the planted S2 window/segments: **1**. Treat these as the false-positive budget. Each needs triage, not an automatic page.
* S3 (VoltEdge refund drift) is a **slow trend**, not an anomaly. A day-over-day detector is the wrong tool for it, so it is caught by trend monitoring (sql/analysis/13_brand_refund_trend.sql) instead.

## What this system can and cannot tell you
* **It can tell you** that a metric is unusual given its own weekday pattern and its volume, how big and
  how long the gap is, and which segments carry it.
* **It cannot tell you why.** "Payment success collapsed for app users in Bihar/UP/WB after 12 Nov"
  is a lead for engineering. It becomes a cause only when release notes, gateway logs, or a rollback
  confirm it.
* Festive peaks are labelled `expected_seasonal` instead of alerted, and they are masked out of the
  baselines so that the week after Diwali isn't judged against Diwali.
