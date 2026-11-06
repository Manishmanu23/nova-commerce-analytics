"""
Does Nova Plus membership CAUSE more ordering, or do loyal customers simply join?

The naive member vs non-member gap mixes a (possibly real) effect with SELF-SELECTION. We estimate the
effect several ways, from worst to best, and are explicit about what each can and cannot remove:

  1. Naive difference in 90-day orders after the index date
  2. Regression adjustment (OLS) on observed pre-index behaviour
  3. Coarsened exact matching on prior orders, recent orders and tenure (ATT)
  4. Difference-in-differences: (post - pre) for members vs matched non-members

Index date: members = join date; non-members = the moment right after their 2nd+ order that falls at a
comparable point (members join right after an order, typically their 2nd-4th). 90-day windows either
side; only customers with complete follow-up are used.

Even (4) cannot remove selection on UNOBSERVED loyalty that changes over time. The honest
conclusion is an upper bound, plus a recommendation for a randomised encouragement design.
"""
import json

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from nova.common.db import read_sql, write_df
from nova.common.report import ROOT, md_table

END = pd.Timestamp("2025-12-31")
LAUNCH = pd.Timestamp("2024-04-01")


def build():
    o = read_sql("""select customer_id, order_at from marts.fct_orders
                    where is_countable and customer_id is not null and not is_orphan_customer
                      and not is_legacy_customer""")
    o["order_at"] = pd.to_datetime(o.order_at)
    subs = read_sql("select customer_id, min(start_at) as join_at from marts.fct_subscriptions group by 1")
    subs["join_at"] = pd.to_datetime(subs.join_at)
    info = read_sql("select customer_id, acquisition_channel, first_order_date from marts.mart_customer_ltv")
    info["first_order_date"] = pd.to_datetime(info.first_order_date)
    o = o.sort_values(["customer_id", "order_at"])
    o["k"] = o.groupby("customer_id").cumcount() + 1
    members = set(subs.customer_id)
    # non-member index: a random eligible order (k >= 2) -> mirrors "joined right after an order"
    rng = np.random.default_rng(3)
    elig = o[(o.k >= 2) & ~o.customer_id.isin(members) & (o.order_at >= LAUNCH)
             & (o.order_at <= END - pd.Timedelta(days=90))]
    nm = elig.groupby("customer_id").apply(lambda g: g.iloc[rng.integers(len(g))], include_groups=False).reset_index()
    nm = nm.rename(columns={"order_at": "index_at"})[["customer_id", "index_at"]]
    nm["member"] = 0
    mb = subs.rename(columns={"join_at": "index_at"})
    mb = mb[(mb.index_at <= END - pd.Timedelta(days=90)) & mb.customer_id.isin(info.customer_id)]
    mb["member"] = 1
    idx = pd.concat([mb, nm], ignore_index=True).merge(info, on="customer_id")
    j = o.merge(idx[["customer_id", "index_at"]], on="customer_id")
    dt = (j.order_at - j.index_at).dt.total_seconds() / 86400
    j["pre90"] = (dt < 0) & (dt >= -90)
    j["post90"] = (dt > 0.01) & (dt <= 90)          # exclude the triggering order itself
    j["prior"] = dt <= 0.01
    agg = j.groupby("customer_id")[["pre90", "post90", "prior"]].sum()
    X = idx.set_index("customer_id").join(agg).fillna(0).reset_index()
    X["tenure_days"] = (X.index_at - X.first_order_date).dt.days
    X["index_q"] = X.index_at.dt.to_period("Q").astype(str)
    return X


def estimates(X):
    out = {}
    m, n = X[X.member == 1], X[X.member == 0]
    # each entry: (absolute effect in orders / 90d, counterfactual baseline used for the relative effect)
    out["1 naive"] = (m.post90.mean() - n.post90.mean(), n.post90.mean())
    fit = smf.ols("post90 ~ member + pre90 + prior + tenure_days + C(acquisition_channel) + C(index_q)", X).fit(cov_type="HC1")
    out["2 regression adjusted"] = (fit.params["member"], n.post90.mean())
    ci_reg = fit.conf_int().loc["member"].tolist()
    X = X.assign(s_prior=X.prior.clip(upper=8), s_pre=X.pre90.clip(upper=4),
                 s_ten=pd.cut(X.tenure_days, [-1, 30, 90, 180, 365, 10_000], labels=False))
    strata = X.groupby(["s_prior", "s_pre", "s_ten", "member"]).post90.agg(["mean", "size"]).unstack("member")
    strata = strata.dropna()
    w = strata[("size", 1)]
    att = ((strata[("mean", 1)] - strata[("mean", 0)]) * w).sum() / w.sum()
    ctrl = (strata[("mean", 0)] * w).sum() / w.sum()
    out["3 coarsened exact matching (ATT)"] = (att, ctrl)
    X["delta"] = X.post90 - X.pre90
    sd = X.groupby(["s_prior", "s_ten", "member"]).delta.agg(["mean", "size"]).unstack("member").dropna()
    w2 = sd[("size", 1)]
    did = ((sd[("mean", 1)] - sd[("mean", 0)]) * w2).sum() / w2.sum()
    # counterfactual for members = their own pre-period level adjusted by the control group's pre->post change
    mem_pre = X[X.member == 1].pre90.mean()
    ctrl_change = ((sd[("mean", 0)]) * w2).sum() / w2.sum()
    out["4 diff-in-diff on matched strata"] = (did, mem_pre + ctrl_change)
    res = pd.DataFrame([dict(method=k, effect_orders_per_90d=v[0], counterfactual_baseline=v[1], relative_effect=v[0] / v[1])
                        for k, v in out.items()])
    matched_share = w.sum() / len(m)
    return res, ci_reg, matched_share, len(m), len(n)


def main() -> str:
    X = build()
    res, ci_reg, share, n_m, n_n = estimates(X)
    write_df(res, "causal_membership_estimates")
    gt = ROOT / "data" / "ground_truth" / "scenarios.json"
    truth = ""
    if gt.exists():
        g = json.loads(gt.read_text())
        truth = (f"\n**Ground truth (simulation only, never available in real life):** membership raises the "
                 f"order rate by {float(g['MEMBER_TRUE_RATE_LIFT']) - 1:.0%} while active and extends lifetime by "
                 f"{float(g['MEMBER_TRUE_LIFETIME_EXT']) - 1:.0%}. The join probability rises steeply with latent loyalty "
                 "(strong selection). Methods 2-4 move toward the truth but stay above it, which is expected because "
                 "loyalty is only partly observable.\n")
    return f"""# Causal question: does Nova Plus membership increase ordering?

Sample: {n_m:,} members and {n_n:,} non-members with a full 90-day follow-up after their index date.
Coarsened matching found comparable non-members for only {share:.0%} of members. Poor overlap is itself a
finding: members are very different customers *before* they join.

{md_table(res)}

Regression 95% CI for the member coefficient: {ci_reg[0]:.3f} to {ci_reg[1]:.3f} orders per 90 days.
{truth}
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
"""
