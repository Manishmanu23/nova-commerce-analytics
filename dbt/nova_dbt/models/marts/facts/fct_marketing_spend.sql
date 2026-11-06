-- grain: ONE ROW PER (DATE, CAMPAIGN). Spend is NET of platform credit notes.
select m.spend_date, to_char(m.spend_date, 'YYYYMMDD')::int as spend_date_key, m.campaign_id, c.channel,
       c.objective, c.objective = 'acquisition' as is_acquisition_spend, m.spend_inr, m.gross_spend_inr,
       m.credit_note_inr, m.impressions, m.clicks, m.null_impression_rows
from {{ ref('stg_marketing_spend') }} m
left join {{ ref('stg_marketing_campaigns') }} c using (campaign_id)
