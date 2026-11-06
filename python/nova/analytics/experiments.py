"""
Experiment analysis with the checks a senior analyst runs BEFORE reading the headline lift.

Order of operations (deliberate):
  1. Validity   - Sample Ratio Mismatch (chi-square vs planned split), covariate balance (pre-period SMD)
  2. Primary    - purchase rate: two-proportion z-test, Newcombe CI (absolute), delta-method CI (relative)
  3. Power      - achieved power for the pre-registered minimum effect of interest (MDE)
  4. Revenue    - Welch t-test + bootstrap CI; CUPED variance reduction using pre-period revenue
  5. Guardrails - contribution margin per user, shipping fee revenue per user
  6. Multiple testing - secondary metrics & subgroups corrected with Holm (FWER) and BH (FDR)
  7. Decision   - statistical AND practical significance, stated in business language
"""
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import confint_proportions_2indep, proportion_effectsize, proportions_ztest

from nova.common.db import read_sql, write_df
from nova.common.report import md_table

PRACTICAL_MDE_REL = 0.05   # pre-registered: product needs >= +5% relative purchase-rate lift to justify the change
ALPHA, SRM_ALPHA = 0.05, 0.001
RNG = np.random.default_rng(7)


def boot_diff_ci(t, c, n=2000, q=(2.5, 97.5)):
    t, c = np.asarray(t, float), np.asarray(c, float)
    bt = RNG.choice(t, (n, len(t)), replace=True).mean(axis=1)
    bc = RNG.choice(c, (n, len(c)), replace=True).mean(axis=1)
    return np.percentile(bt - bc, q)


def welch(t, c):
    r = stats.ttest_ind(t, c, equal_var=False)
    return float(np.mean(t) - np.mean(c)), float(r.pvalue)


def cuped(y, x):
    theta = np.cov(y, x)[0, 1] / np.var(x, ddof=1) if np.var(x) > 0 else 0.0
    return y - theta * (x - x.mean()), theta


def smd(a, b):
    s = np.sqrt((np.var(a, ddof=1) + np.var(b, ddof=1)) / 2)
    return (np.mean(a) - np.mean(b)) / s if s else 0.0


def analyse(g: pd.DataFrame, meta: pd.Series) -> tuple[dict, list[dict]]:
    t, c = g[g.variant == "treatment"], g[g.variant == "control"]
    n_t, n_c, ps = len(t), len(c), float(meta.planned_split)
    srm_p = stats.chisquare([n_t, n_c], f_exp=[(n_t + n_c) * ps, (n_t + n_c) * (1 - ps)]).pvalue
    bal = smd(t.pre_period_orders, c.pre_period_orders)
    x_t, x_c = int(t.converted.sum()), int(c.converted.sum())
    p_t, p_c = x_t / n_t, x_c / n_c
    z, p = proportions_ztest([x_t, x_c], [n_t, n_c])
    lo, hi = confint_proportions_2indep(x_t, n_t, x_c, n_c, method="newcomb", compare="diff")
    rel = p_t / p_c - 1
    se_log = np.sqrt((1 - p_t) / max(x_t, 1) + (1 - p_c) / max(x_c, 1))
    rel_lo, rel_hi = np.exp(np.log(p_t / p_c) + np.array([-1.96, 1.96]) * se_log) - 1
    es = proportion_effectsize(p_c * (1 + PRACTICAL_MDE_REL), p_c)
    power = NormalIndPower().power(effect_size=es, nobs1=n_t, alpha=ALPHA, ratio=n_c / n_t)
    n_needed = NormalIndPower().solve_power(effect_size=es, alpha=ALPHA, power=0.8, ratio=1.0)
    rev_diff, rev_p = welch(t.net_revenue, c.net_revenue)
    rev_ci = boot_diff_ci(t.net_revenue, c.net_revenue)
    y = g.net_revenue.to_numpy(float)
    adj, theta = cuped(y, g.pre_period_net_revenue.to_numpy(float))
    is_t = (g.variant == "treatment").to_numpy()
    cup_diff, cup_p = welch(adj[is_t], adj[~is_t])
    var_red = 1 - np.var(adj) / np.var(y) if np.var(y) else 0
    cm_diff, cm_p = welch(t.contribution_margin, c.contribution_margin)
    ship_diff, ship_p = welch(t.shipping_fee_paid, c.shipping_fee_paid)

    if srm_p < SRM_ALPHA:
        decision = "INVALID: sample ratio mismatch"
        why = (f"Observed split {n_t}/{n_c} vs planned {ps:.0%} (chi-square p = {srm_p:.1e}). Randomisation or "
               "exposure logging is broken, so the arms are not comparable and **no lift estimate from this test "
               "should be used**. Next step: compare assignment logs with exposure logs by platform and day, fix "
               "the logging, and re-run.")
    elif p < ALPHA and rel_lo > 0:
        if rel_lo >= PRACTICAL_MDE_REL:
            decision = "SHIP"
            why = "The effect is statistically significant, and even the lower end of the CI clears the practical threshold."
        else:
            decision = "SHIP WITH MONITORING (effect real, size uncertain)"
            why = (f"The lift is significant, but the CI ({rel_lo:+.1%} to {rel_hi:+.1%} relative) includes values below the "
                   f"+{PRACTICAL_MDE_REL:.0%} practical threshold. Ship only if rollout cost is low, and keep a 10% holdout "
                   "to confirm the size.")
    elif p >= ALPHA and power < 0.8:
        decision = "INCONCLUSIVE (underpowered)"
        why = (f"Power to detect +{PRACTICAL_MDE_REL:.0%} was only {power:.0%}. 'Not significant' here does **not** "
               f"mean 'no effect'. About {n_needed:,.0f} users per arm would be needed.")
    elif p >= ALPHA:
        decision = "DO NOT SHIP (no effect of practical size detected)"
        why = f"The test was adequately powered ({power:.0%}) for +{PRACTICAL_MDE_REL:.0%}, and no such effect is present."
    else:
        decision = "DO NOT SHIP (negative)"
        why = "The treatment performed significantly worse."
    summary = dict(experiment_id=meta.experiment_id, experiment_name=meta.experiment_name, n_treatment=n_t,
                   n_control=n_c, srm_p=srm_p, pre_period_smd=bal, cr_control=p_c, cr_treatment=p_t,
                   abs_lift=p_t - p_c, abs_ci_low=lo, abs_ci_high=hi, rel_lift=rel, rel_ci_low=rel_lo,
                   rel_ci_high=rel_hi, p_value=p, power_at_mde=power, n_per_arm_needed=n_needed,
                   rev_per_user_diff=rev_diff, rev_p=rev_p, rev_boot_ci_low=rev_ci[0], rev_boot_ci_high=rev_ci[1],
                   cuped_theta=theta, cuped_rev_diff=cup_diff, cuped_rev_p=cup_p, cuped_variance_reduction=var_red,
                   cm_per_user_diff=cm_diff, cm_p=cm_p, ship_fee_per_user_diff=ship_diff, ship_fee_p=ship_p,
                   decision=decision, rationale=why)
    # secondary metrics + subgroups (for multiple-testing demonstration)
    sec = []
    for m in ["converted", "orders_in_window", "net_revenue", "contribution_margin", "shipping_fee_paid"]:
        d, pv = welch(t[m], c[m])
        sec.append(dict(experiment_id=meta.experiment_id, test=f"metric:{m}", diff=d, p_raw=pv))
    for plat, gg in g.groupby("platform"):
        tt, cc = gg[gg.variant == "treatment"], gg[gg.variant == "control"]
        if len(tt) > 30 and len(cc) > 30:
            _, pv = proportions_ztest([tt.converted.sum(), cc.converted.sum()], [len(tt), len(cc)])
            sec.append(dict(experiment_id=meta.experiment_id, test=f"subgroup:{plat} conversion",
                            diff=tt.converted.mean() - cc.converted.mean(), p_raw=pv))
    return summary, sec


def main() -> str:
    df = read_sql("select * from marts.fct_experiment_exposures")
    meta = read_sql("select * from marts.dim_experiment").set_index("experiment_id", drop=False)
    res, secs = [], []
    for eid, g in df.groupby("experiment_id"):
        s, sec = analyse(g, meta.loc[eid])
        res.append(s)
        secs.extend(sec)
    R = pd.DataFrame(res)
    S = pd.DataFrame(secs)
    S["p_holm"] = S.groupby("experiment_id").p_raw.transform(lambda p: multipletests(p, method="holm")[1])
    S["p_bh"] = S.groupby("experiment_id").p_raw.transform(lambda p: multipletests(p, method="fdr_bh")[1])
    S["significant_raw"] = S.p_raw < ALPHA
    S["significant_holm"] = S.p_holm < ALPHA
    write_df(R, "experiment_results")
    write_df(S, "experiment_secondary_tests")

    parts = ["# Experiment Readouts\n",
             f"Pre-registered practical threshold (MDE): **+{PRACTICAL_MDE_REL:.0%} relative purchase rate**. "
             f"α = {ALPHA}. SRM alarm at p < {SRM_ALPHA}. Unit = customer. Outcomes are counted only after assignment "
             "and before the experiment ends.\n"]
    for r in R.itertuples():
        parts.append(f"""## {r.experiment_id}: `{r.experiment_name}`

**Decision: {r.decision}**. {r.rationale}

| Check | Result |
|---|---|
| Sample sizes (T / C) | {r.n_treatment:,} / {r.n_control:,} |
| SRM chi-square p | {r.srm_p:.2e} |
| Pre-period balance (SMD of prior orders) | {r.pre_period_smd:+.3f} (|SMD| < 0.1 = balanced) |
| Purchase rate C → T | {r.cr_control:.2%} → {r.cr_treatment:.2%} |
| Absolute lift (95% CI) | {r.abs_lift:+.2%} ({r.abs_ci_low:+.2%} to {r.abs_ci_high:+.2%}) |
| Relative lift (95% CI) | {r.rel_lift:+.1%} ({r.rel_ci_low:+.1%} to {r.rel_ci_high:+.1%}) |
| p-value (two-proportion z) | {r.p_value:.4f} |
| Power to detect +{PRACTICAL_MDE_REL:.0%} | {r.power_at_mde:.0%} (need ≈ {r.n_per_arm_needed:,.0f} per arm for 80%) |
| Net revenue / user diff (Welch p; bootstrap 95% CI) | ₹{r.rev_per_user_diff:+.1f} (p = {r.rev_p:.3f}; ₹{r.rev_boot_ci_low:+.1f} to ₹{r.rev_boot_ci_high:+.1f}) |
| CUPED-adjusted revenue diff (variance reduction) | ₹{r.cuped_rev_diff:+.1f} (p = {r.cuped_rev_p:.3f}; {r.cuped_variance_reduction:.0%} variance removed) |
| Guardrail: CM / user diff | ₹{r.cm_per_user_diff:+.1f} (p = {r.cm_p:.3f}) |
| Guardrail: shipping-fee revenue / user diff | ₹{r.ship_fee_per_user_diff:+.2f} (p = {r.ship_fee_p:.3f}) |
""")
        sub = S[S.experiment_id == r.experiment_id][["test", "diff", "p_raw", "p_holm", "p_bh", "significant_raw",
                                                     "significant_holm"]]
        parts.append("**Secondary metrics & subgroups (multiple-testing corrected):**\n\n" + md_table(sub) + "\n")
        parts.append(STAKEHOLDER.get(r.decision.split(" ")[0], ""))
    txt = "\n".join(parts) + GLOSSARY
    return txt


STAKEHOLDER = {
    "INVALID:": "\n> **What a stakeholder should conclude:** nothing about the treatment. The comparison is biased. "
                "**Should NOT conclude:** \"the lift was positive, so let's ship anyway\". SRM usually means the "
                "users *missing* from one arm are systematically different (here: treatment users who never "
                "purchased were less likely to be logged), and that inflates the apparent lift.\n",
    "SHIP": "\n> **Should conclude:** the change very likely increases purchase rate. The CI gives the plausible "
            "size, and the holdout will pin it down. **Should NOT conclude:** that the point estimate is the "
            "exact size, or that revenue will rise by the same %. Revenue is noisier; check its CI separately.\n",
    "INCONCLUSIVE": "\n> **Should conclude:** the test could not distinguish a useful effect from zero. "
                    "**Should NOT conclude:** \"it doesn't work\". Absence of evidence is not evidence of absence "
                    "when power is low.\n",
    "DO": "\n> **Should conclude:** if there is an effect, it is smaller than what the business said it needs. "
          "**Should NOT conclude:** that one 'significant' subgroup (see table) is a real finding. After a Holm "
          "correction it usually isn't. Treat it as a hypothesis for a new test.\n",
}
GLOSSARY = """
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
"""
