{{ config(severity='warn') }}
-- Sample Ratio Mismatch (SRM) guard. Chi-square goodness-of-fit vs the planned split (1 df).
-- 10.83 = critical value at p = 0.001. An SRM means randomisation or logging is broken:
-- the experiment result must NOT be trusted until the cause is found.
with c as (
    select a.experiment_id, e.planned_split,
           count(*) filter (where a.variant = 'treatment') as n_t, count(*) filter (where a.variant = 'control') as n_c
    from {{ ref('fct_experiment_exposures') }} a join {{ ref('dim_experiment') }} e using (experiment_id)
    group by 1, 2
)
select experiment_id, n_t, n_c,
       power(n_t - (n_t + n_c) * planned_split, 2) / ((n_t + n_c) * planned_split)
     + power(n_c - (n_t + n_c) * (1 - planned_split), 2) / ((n_t + n_c) * (1 - planned_split)) as chi_sq
from c
where power(n_t - (n_t + n_c) * planned_split, 2) / ((n_t + n_c) * planned_split)
    + power(n_c - (n_t + n_c) * (1 - planned_split), 2) / ((n_t + n_c) * (1 - planned_split)) > 10.83
