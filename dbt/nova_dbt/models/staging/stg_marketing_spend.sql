-- grain: one row per (spend_date, campaign_id).
-- The source contract claims this key is unique, but platforms post credit notes as extra NEGATIVE
-- rows for the same day. They are legitimate, so we NET them instead of dropping them.
select {{ safe_date('spend_date') }} as spend_date, campaign_id,
       sum({{ safe_numeric('spend_inr') }})                                         as spend_inr,
       sum(greatest({{ safe_numeric('spend_inr') }}, 0))                            as gross_spend_inr,
       sum(least({{ safe_numeric('spend_inr') }}, 0))                               as credit_note_inr,
       sum({{ safe_int('impressions') }})                                           as impressions,
       sum({{ safe_int('clicks') }})                                                as clicks,
       count(*) filter (where impressions is null or impressions = '')              as null_impression_rows
from {{ source('raw','marketing_spend') }}
group by 1, 2
