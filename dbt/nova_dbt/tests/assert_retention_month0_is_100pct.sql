-- By definition every customer is active in their cohort month. Anything else = cohort logic bug.
select cohort_month, acquisition_segment, retention_rate
from {{ ref('mart_cohort_retention') }}
where months_since_first = 0 and retention_rate <> 1
