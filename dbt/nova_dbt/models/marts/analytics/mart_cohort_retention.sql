-- grain: ONE ROW PER (COHORT MONTH, ACQUISITION SEGMENT, MONTHS SINCE FIRST ORDER).
-- Stores ADDITIVE counts (active, cohort_size) so any roll-up recomputes the rate correctly.
-- Never average retention percentages across cohorts - weight by cohort size.
with m as (select * from {{ ref('fct_customer_monthly') }} where not is_legacy_customer),
seg as (select customer_id, acquisition_channel,
               case when is_deep_discount_acquired then 'deep_discount_campaign' else acquisition_channel end as acquisition_segment
        from {{ ref('mart_customer_ltv') }})
select m.cohort_month, s.acquisition_channel, s.acquisition_segment, m.months_since_first,
       count(*)                                   as cohort_size,
       count(*) filter (where m.is_active)        as active_customers,
       round(count(*) filter (where m.is_active)::numeric / nullif(count(*), 0), 4) as retention_rate,
       sum(m.cumulative_net_revenue)              as cumulative_net_revenue,
       sum(m.cumulative_cm)                       as cumulative_cm
from m join seg s using (customer_id)
group by 1, 2, 3, 4
