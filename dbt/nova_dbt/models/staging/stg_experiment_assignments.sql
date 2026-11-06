-- grain: one row per (experiment, customer). First assignment wins (re-assignment would break randomisation).
with typed as (
    select assignment_id, experiment_id, customer_id, lower(variant) as variant,
           {{ to_ist('assigned_ts') }} as assigned_at, platform
    from {{ source('raw','experiment_assignments') }}
)
select assignment_id, experiment_id, customer_id, variant, assigned_at, platform
from ({{ dedupe('typed', 'experiment_id, customer_id', 'assigned_at') }}) d
