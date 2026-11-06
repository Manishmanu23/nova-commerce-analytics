select experiment_id, experiment_name, hypothesis, primary_metric, randomisation_unit, planned_split,
       start_date, end_date, (end_date - start_date + 1) as duration_days, owner, status
from {{ ref('stg_experiments') }}
