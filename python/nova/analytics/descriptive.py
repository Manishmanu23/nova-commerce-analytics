"""
Descriptive & inferential statistics that answer real stakeholder questions.
Each block ends with: what a stakeholder SHOULD and SHOULD NOT conclude.
"""
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.proportion import proportion_confint

from nova.common.db import read_sql
from nova.common.report import md_table

RNG = np.random.default_rng(11)


def boot_ci(x, fn=np.median, n=2000):
    x = np.asarray(x, float)
    b = np.array([fn(RNG.choice(x, len(x))) for _ in range(n)])
    return np.percentile(b, [2.5, 97.5])


def aov_distribution():
    o = read_sql("""select order_channel, is_bulk_order, items_gross_revenue_inr - coupon_discount_inr as value
                    from marts.fct_orders where is_countable and order_date >= '2025-07-01'""")
    v = o[~o.is_bulk_order].value
    desc = pd.DataFrame([dict(
        orders=len(v), mean=v.mean(), median=v.median(), std=v.std(), p90=v.quantile(.9), p99=v.quantile(.99),
        skewness=stats.skew(v), skew_of_log=stats.skew(np.log(v.clip(lower=1))),
        mean_ci_low=v.mean() - 1.96 * v.std() / np.sqrt(len(v)), mean_ci_high=v.mean() + 1.96 * v.std() / np.sqrt(len(v)),
        median_ci_low=boot_ci(v)[0], median_ci_high=boot_ci(v)[1],
        mean_incl_bulk=o.value.mean())])
    app = o[(o.order_channel == "app") & ~o.is_bulk_order].value
    web = o[(o.order_channel == "web") & ~o.is_bulk_order].value
    mw = stats.mannwhitneyu(app, web, alternative="two-sided")
    cliffs = 2 * mw.statistic / (len(app) * len(web)) - 1
    tt = stats.ttest_ind(np.log(app), np.log(web), equal_var=False)
    return f"""## 1. Order value distribution (H2 2025, excluding B2B bulk orders)
{md_table(desc)}

* Order value is strongly **right-skewed** (skewness {desc.skewness.iat[0]:.1f}; {desc.skew_of_log.iat[0]:.1f} on the log scale,
  so it is roughly log-normal). The mean sits well above the median.
* The 95% CI for the mean AOV is narrow (₹{desc.mean_ci_low.iat[0]:,.0f} to ₹{desc.mean_ci_high.iat[0]:,.0f}) because n is
  large. Precision is not the problem, and the choice of statistic matters more: the median is ₹{desc["median"].iat[0]:,.0f}.
  Including the {int(o.is_bulk_order.sum())} bulk orders moves the half-year mean from ₹{desc["mean"].iat[0]:,.0f} to
  ₹{desc.mean_incl_bulk.iat[0]:,.0f}, which is small over six months. On a single day, though, one bulk order can move
  AOV by more than 50%, and that is why the governed AOV excludes them.

**App vs web order value.** Mann-Whitney p = {mw.pvalue:.3g}, Cliff's δ = {cliffs:+.3f}, and a Welch t-test on
log(value) gives p = {tt.pvalue:.3g}. App median minus web median is roughly ₹{np.median(app) - np.median(web):+,.0f}.

> **Should conclude:** report AOV with the median alongside it and state the bulk-order rule. Any app/web
> difference is described by its *size* (δ), not just its p-value. |δ| < 0.15 is negligible even when p is tiny.
> **Should NOT conclude:** that app users "spend more *because* of the app". Channel choice is self-selected.
"""


def refund_rates():
    r = read_sql("""select category, count(*) as lines, sum(is_refunded::int) as refunded
                    from marts.fct_order_items where is_countable and order_date between '2025-01-01' and '2025-11-30'
                    group by 1 order by 1""")
    lo, hi = proportion_confint(r.refunded, r.lines, method="wilson")
    r["refund_line_rate"] = r.refunded / r.lines
    r["ci_low"], r["ci_high"] = lo, hi
    tab = r.values[:, 1:3].astype(int)
    chi = stats.chi2_contingency(np.column_stack([tab[:, 1], tab[:, 0] - tab[:, 1]]))
    return f"""## 2. Refund rate by category, with Wilson 95% CIs (orders Jan–Nov 2025)
{md_table(r)}

Chi-square test of independence (category × refunded): χ² = {chi.statistic:,.0f}, dof = {chi.dof}, p = {chi.pvalue:.2g}.

> **Should conclude:** categories differ in return propensity. Where two CIs do not overlap, the gap is not
> sampling noise. **Should NOT conclude:** that a category is "bad". Fashion's high rate is size-driven and
> structural. The actionable signal is a *change* within a brand (see sql/analysis/13, VoltEdge).
> December is excluded because refunds arrive late (right-censoring).
"""


def censoring_bias():
    c = read_sql("select cohort_month, is_mature_90d, repeated_within_90d from marts.mart_customer_ltv")
    naive = c.groupby("cohort_month").repeated_within_90d.mean()
    mature = c[c.is_mature_90d].groupby("cohort_month").repeated_within_90d.mean()
    t = pd.DataFrame({"naive_repeat_rate": naive, "mature_only_repeat_rate": mature}).tail(6).reset_index()
    return f"""## 3. A sampling trap: right-censoring in repeat rate
{md_table(t)}

The "naive" rate includes customers who have not yet had 90 days to repeat, so recent cohorts look
worse than they are. The governed metric (`repeat_purchase_rate_90d`) uses only mature cohorts. Blank
cells mean "not yet measurable", not zero.

> **Should NOT conclude** from a naive dashboard that "recent cohorts are much less loyal". Part of the drop
> is a measurement artefact. The true, planted part of the drop (the S1 discount cohort) only shows once
> those cohorts mature.
"""


def mix_vs_rate():
    s = read_sql("""select case when session_date between '2025-04-01' and '2025-06-30' then 'Q2' else 'Q4' end as q,
                           device_type, count(*) as sessions, sum(has_purchase::int) as purchases
                    from marts.fct_sessions where not is_bot and (session_date between '2025-04-01' and '2025-06-30'
                          or session_date between '2025-10-01' and '2025-12-31') group by 1, 2""")
    p = s.pivot(index="device_type", columns="q", values=["sessions", "purchases"])
    w0, w1 = p.sessions.Q2 / p.sessions.Q2.sum(), p.sessions.Q4 / p.sessions.Q4.sum()
    r0, r1 = p.purchases.Q2 / p.sessions.Q2, p.purchases.Q4 / p.sessions.Q4
    total0, total1 = (w0 * r0).sum(), (w1 * r1).sum()
    mix = ((w1 - w0) * r0).sum()
    rate = (w1 * (r1 - r0)).sum()
    t = pd.DataFrame({"share_Q2": w0, "share_Q4": w1, "conv_Q2": r0, "conv_Q4": r1}).reset_index()
    return f"""## 4. Mix vs rate: why overall conversion moved (Q2 → Q4 2025)
{md_table(t)}

Overall conversion went from {total0:.3%} to {total1:.3%} ({total1 - total0:+.3%}). Of that change, the **mix effect**
(a shift in device share) was {mix:+.3%} and the **rate effect** (conversion within each device) was {rate:+.3%}.

> **Should conclude:** before blaming the funnel, check whether the traffic mix changed. The two effects can
> point in opposite directions (Simpson's paradox). **Should NOT conclude** anything from the overall rate alone.
"""


def main() -> str:
    return "\n".join(["# Statistical Analysis\n", aov_distribution(), refund_rates(), censoring_bias(), mix_vs_rate()])
