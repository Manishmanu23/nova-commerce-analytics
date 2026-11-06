/* =====================================================================================
Q21  Experiment readout in SQL: SRM check, conversion by arm, absolute lift and 95% CI
-------------------------------------------------------------------------------------
BUSINESS QUESTION  Did the treatment work, and can we trust the experiment?
WHY IT WORKS       Normal approximation for the difference of two proportions:
                   se = sqrt(p1(1-p1)/n1 + p0(1-p0)/n0); CI = diff +/- 1.96 se.
ORDER OF CHECKS    1) SRM (chi-square vs planned split) - if it fails, STOP: the comparison is biased.
                   2) Primary metric lift + CI.   3) Guardrails (CM per user, shipping revenue).
LIMITS             Full analysis (CUPED, t-tests on revenue, multiple-testing correction, power) is in
                   python/nova/analytics/experiments.py - SQL is great for the counts, Python for inference.
===================================================================================== */
with a as (
    select x.experiment_id, x.variant, count(*) as n, avg(x.converted) as cr, avg(x.net_revenue) as rev_per_user,
           avg(x.contribution_margin) as cm_per_user, e.planned_split
    from marts.fct_experiment_exposures x join marts.dim_experiment e using (experiment_id)
    group by 1, 2, e.planned_split
),
w as (
    select t.experiment_id, t.n as n_t, c.n as n_c, t.cr as cr_t, c.cr as cr_c,
           t.rev_per_user as rpu_t, c.rev_per_user as rpu_c, t.cm_per_user as cmpu_t, c.cm_per_user as cmpu_c,
           t.planned_split as ps
    from a t join a c on c.experiment_id = t.experiment_id and t.variant = 'treatment' and c.variant = 'control'
)
select experiment_id, n_t, n_c,
       round(power(n_t - (n_t + n_c) * ps, 2) / ((n_t + n_c) * ps)
           + power(n_c - (n_t + n_c) * (1 - ps), 2) / ((n_t + n_c) * (1 - ps)), 2) as srm_chi_sq,
       case when power(n_t - (n_t + n_c) * ps, 2) / ((n_t + n_c) * ps)
               + power(n_c - (n_t + n_c) * (1 - ps), 2) / ((n_t + n_c) * (1 - ps)) > 10.83
            then 'SRM - DO NOT TRUST' else 'ok' end as srm_status,
       round(cr_c, 4) as cr_control, round(cr_t, 4) as cr_treatment, round(cr_t - cr_c, 4) as abs_lift,
       round((cr_t - cr_c) / nullif(cr_c, 0), 4) as rel_lift,
       round(cr_t - cr_c - 1.96 * sqrt(cr_t * (1 - cr_t) / n_t + cr_c * (1 - cr_c) / n_c), 4) as ci95_low,
       round(cr_t - cr_c + 1.96 * sqrt(cr_t * (1 - cr_t) / n_t + cr_c * (1 - cr_c) / n_c), 4) as ci95_high,
       round(cmpu_t - cmpu_c, 2) as cm_per_user_diff
from w order by experiment_id;
