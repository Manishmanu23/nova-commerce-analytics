/* =====================================================================================
Q09  180-day contribution LTV vs CAC by acquisition channel (mature cohorts only)
-------------------------------------------------------------------------------------
BUSINESS QUESTION  Which channels acquire customers who pay back their acquisition cost?
WHY IT WORKS       LTV = avg 180-day CM of customers acquired >= 180 days ago. CAC = acquisition spend of the
                   channel / new customers acquired by it over the SAME cohort months.
WHY THIS WAY       * Contribution-margin LTV (not revenue LTV): revenue LTV makes discount-heavy channels look great.
                   * Maturity filter: including 30-day-old customers in a 180-day LTV biases it downward.
                   * CAC and LTV use the same cohort window - mixing a 2024 CAC with a 2025 LTV is meaningless.
LIMITATION         Last-touch attribution over-credits bottom-funnel channels; organic has no CAC.
===================================================================================== */
with ltv as (
    select first_order_channel as channel, count(*) as mature_customers, avg(cm_180d) as ltv_180d_cm,
           min(cohort_month) as first_cohort, max(cohort_month) as last_cohort
    from marts.mart_customer_ltv where is_mature_180d group by 1
),
cac as (
    select e.channel, sum(e.acquisition_spend) as spend, sum(e.new_customers) as new_customers
    from marts.mart_channel_monthly_economics e
    join ltv on ltv.channel = e.channel and e.month between ltv.first_cohort and ltv.last_cohort
    group by 1
)
select l.channel, l.mature_customers, round(l.ltv_180d_cm, 0) as ltv_180d_cm,
       round(c.spend / nullif(c.new_customers, 0), 0) as cac,
       round(l.ltv_180d_cm / nullif(c.spend / nullif(c.new_customers, 0), 0), 2) as ltv_to_cac
from ltv l left join cac c using (channel)
order by ltv_to_cac desc nulls last;
