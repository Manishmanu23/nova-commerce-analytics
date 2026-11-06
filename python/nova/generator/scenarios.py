"""
Planted business scenarios (the "ground truth").

WHY THIS FILE EXISTS
--------------------
Synthetic data is only useful for a portfolio if it contains *known* effects.
Every analytical method in this repo (anomaly detection, experiment analysis,
cohort analysis, causal adjustment) is validated by checking whether it
recovers the effects defined here. The analysis code NEVER imports this file;
only the generator and the evaluation scripts do.
"""
from datetime import date

# S1 - Discount-heavy paid-social campaign acquires cheap but low-quality customers
S1_CAMPAIGN_ID = "CMP-PSO-BLITZ40"
S1_START, S1_END = date(2025, 8, 1), date(2025, 10, 31)
S1_DISCOUNT = 0.40
S1_SHARE_OF_CUSTOMERS = 0.08          # extra customers on top of organic flow
S1_LAMBDA_MEAN = 0.16                 # orders / 30 days (vs ~0.30-0.45 normal)
S1_MONTHLY_CHURN = 0.30               # vs ~0.10-0.15 normal
S1_REFUND_MULT = 1.35

# S2 - App release v5.2.0 breaks the UPI intent hand-off on the app; worst in three states
#      (their dominant bank PSP app handles the malformed intent worst)
S2_STATES = ("Uttar Pradesh", "Bihar", "West Bengal")
S2_START, S2_END = date(2025, 11, 12), date(2025, 12, 3)  # release -> hotfix v5.2.1
S2_UPI_FAIL_PROB = 0.70               # app + UPI in the 3 states (vs 0.06 normal first-attempt failure)
S2_UPI_FAIL_PROB_OTHER = 0.22         # app + UPI elsewhere
S2_APP_VERSION_BAD, S2_APP_VERSION_FIX = "5.2.0", "5.2.1"

# S3 - Supplier quality issue in one Electronics brand
S3_BRAND = "VoltEdge"
S3_START = date(2025, 6, 1)
S3_REFUND_PROB_END = 0.22             # ramps linearly from base 0.06 to this by 2025-12-31

# S4 - Fake revenue spike: the full order batch for one day was re-sent by the OMS
S4_DUP_DAY = date(2025, 3, 18)

# S5 - Experiments
EXPERIMENTS = [
    # id, name, start, end, true relative lift on purchase rate, notes
    dict(experiment_id="EXP-2025-01", name="one_page_checkout",
         hypothesis="A single-page checkout increases 14-day purchase rate of active customers by >= 5% relative.",
         primary_metric="purchase_rate", start=date(2025, 6, 2), end=date(2025, 7, 13),
         true_lift=0.10, planned_split=0.5, srm_bug=False),
    dict(experiment_id="EXP-2025-02", name="free_shipping_threshold_299",
         hypothesis="Lowering the free-shipping threshold from 499 to 299 INR increases purchase rate without hurting contribution margin.",
         primary_metric="purchase_rate", start=date(2025, 9, 1), end=date(2025, 9, 28),
         true_lift=0.02, planned_split=0.5, srm_bug=True),
    dict(experiment_id="EXP-2025-03", name="homepage_reco_widget",
         hypothesis="A personalised recommendation widget on the homepage increases purchase rate.",
         primary_metric="purchase_rate", start=date(2025, 2, 3), end=date(2025, 3, 2),
         true_lift=0.0, planned_split=0.5, srm_bug=False),
]
S5_SRM_DROP_PROB = 0.25   # EXP-02 bug: treatment users with no purchase were not logged 25% of the time

# S6 - Nova Plus membership: strong self-selection, modest true causal effect
MEMBERSHIP_LAUNCH = date(2024, 4, 1)
MEMBER_TRUE_RATE_LIFT = 1.15          # true causal lift on order rate while member
MEMBER_TRUE_LIFETIME_EXT = 1.25       # remaining lifetime stretched by 25%
# join probability rises steeply with latent loyalty -> naive comparison overstates effect

# Legacy base: NovaCommerce existed before the new data platform. Customers who signed up in 2023
# exist, but their pre-2024 order history was NOT migrated (left-censored history).
LEGACY_SHARE = 0.30            # share of registered customers who signed up during 2023
LEGACY_DAYS = 365

# DQ-only events (NOT business events) - anomaly system must classify these as data issues
DQ_BOT_SPIKE_DAY = date(2025, 5, 22)  # ~20k headless-browser desktop sessions, zero conversion
