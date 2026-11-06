"""
RFM segmentation (rule-based, transparent) -> analytics.customer_segments.

Why not k-means? Clusters on skewed spend data are unstable, need re-labelling every run, and CRM can't
act on "cluster 3". RFM rules map directly to actions (win-back, VIP care, onboarding). We validate that
segments are meaningfully different in FUTURE behaviour (holdout check), which is what matters.
"""
import numpy as np
import pandas as pd

from nova.common.db import read_sql, write_df
from nova.common.report import md_table

AS_OF = pd.Timestamp("2025-09-30")        # score on data up to Q3, validate on Q4 behaviour


def rfm(as_of: pd.Timestamp) -> pd.DataFrame:
    o = read_sql("""select customer_id, order_date, contribution_margin from marts.fct_orders
                    where is_countable and customer_id is not null and not is_orphan_customer and order_date <= :d""",
                 dict(d=as_of.date()))
    o["order_date"] = pd.to_datetime(o.order_date)
    g = o.groupby("customer_id").agg(last=("order_date", "max"), frequency=("order_date", "count"),
                                     monetary_cm=("contribution_margin", "sum"))
    g["recency_days"] = (as_of - g["last"]).dt.days
    # rank(method="first") breaks ties so quintiles have equal size (NTILE-like); frequency uses thresholds
    g["r"] = 6 - pd.qcut(g.recency_days.rank(method="first"), 5, labels=False).add(1)
    g["f"] = np.select([g.frequency >= 6, g.frequency >= 4, g.frequency == 3, g.frequency == 2], [5, 4, 3, 2], 1)
    g["m"] = pd.qcut(g.monetary_cm.rank(method="first"), 5, labels=False).add(1)
    g["segment"] = np.select(
        [(g.r >= 4) & (g.f >= 4), (g.r >= 3) & (g.f >= 3), (g.r >= 4) & (g.f <= 2),
         (g.r <= 2) & (g.f >= 3), (g.r <= 2) & (g.f <= 2) & (g.m >= 4), g.r <= 2],
        ["Champions", "Loyal", "New / Promising", "At Risk (was loyal)", "Cannot Lose (big spend, lapsed)",
         "Hibernating"], "Needs Attention")
    return g.drop(columns="last").reset_index()


ACTIONS = {"Champions": "VIP perks, referrals; do NOT discount",
           "Loyal": "Cross-sell, membership offer",
           "New / Promising": "Onboarding journey, 2nd-order nudge within 30 days",
           "At Risk (was loyal)": "Personal win-back (non-discount first), survey",
           "Cannot Lose (big spend, lapsed)": "High-touch win-back, CX call",
           "Hibernating": "Low-cost reactivation only; suppress paid retargeting",
           "Needs Attention": "Light-touch nurture"}


def main() -> str:
    s = rfm(AS_OF)
    fut = read_sql("""select customer_id, count(*) as q4_orders, sum(contribution_margin) as q4_cm from marts.fct_orders
                      where is_countable and order_date > '2025-09-30' and customer_id is not null group by 1""")
    s = s.merge(fut, on="customer_id", how="left").fillna({"q4_orders": 0, "q4_cm": 0})
    prof = s.groupby("segment").agg(customers=("customer_id", "count"), avg_recency=("recency_days", "mean"),
                                    avg_orders=("frequency", "mean"), total_cm=("monetary_cm", "sum"),
                                    q4_active_rate=("q4_orders", lambda x: (x > 0).mean()),
                                    q4_cm_per_customer=("q4_cm", "mean")).sort_values("total_cm", ascending=False)
    prof["share_of_cm"] = prof.total_cm / prof.total_cm.sum()
    prof["recommended_action"] = prof.index.map(ACTIONS)
    current = rfm(pd.Timestamp("2025-12-31"))
    write_df(current.assign(as_of="2025-12-31"), "customer_segments")
    return f"""# Customer Segmentation (RFM)

Scored as of {AS_OF.date()}, then **validated on Q4 2025 behaviour**, which the scoring never saw.

{md_table(prof.reset_index())}

* If the segmentation is useful, future activity should fall monotonically from Champions to Hibernating.
  The `q4_active_rate` column checks exactly that, out of sample.
* Contribution margin, not revenue, is the monetary input. A customer who only buys on 40% coupons and
  returns half of it should not rank as a "big spender".

> **Should conclude:** segments rank customers by the likelihood and value of future orders, and
> each one comes with a concrete CRM action. **Should NOT conclude:** that moving a customer into
> "Champions" *causes* higher value. Segments are descriptive. Test interventions per segment with holdouts.
"""
