select experiment_id, experiment_name, hypothesis, primary_metric, randomisation_unit,
       {{ safe_numeric('planned_split') }} as planned_split, {{ safe_date('start_date') }} as start_date,
       {{ safe_date('end_date') }} as end_date, owner, status
from ({{ dedupe(source('raw','experiments'), 'experiment_id', '_loaded_at desc') }}) d
