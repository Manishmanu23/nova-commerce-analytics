/* =====================================================================================
Q08  RFM segmentation with NTILE quintiles
-------------------------------------------------------------------------------------
BUSINESS QUESTION  Who are our Champions, who is At Risk, and how much contribution does each segment drive?
WHY IT WORKS       NTILE(5) ranks customers into quintiles per dimension; recency is reversed (recent = 5).
WHY THIS WAY       Rule-based RFM is transparent - CRM can act on "At Risk = was valuable, now inactive"
                   without trusting a black-box cluster. (Python version: python/nova/analytics/segmentation.py)
PITFALL            NTILE splits TIES arbitrarily: many customers with frequency = 1 land in different F buckets.
                   For frequency we therefore use explicit thresholds instead of NTILE.
AT SCALE           NTILE requires a global sort per dimension; compute weekly into a table, not per dashboard click.
===================================================================================== */
with base as (
    select customer_id, days_since_last_order as recency_days, total_orders as frequency, total_cm as monetary_cm,
           total_net_revenue
    from marts.mart_customer_ltv
),
scored as (
    select *, 6 - ntile(5) over (order by recency_days) as r_score,     -- small recency => high score
           case when frequency >= 6 then 5 when frequency >= 4 then 4 when frequency = 3 then 3
                when frequency = 2 then 2 else 1 end as f_score,
           ntile(5) over (order by monetary_cm) as m_score
    from base
),
seg as (
    select *, case
        when r_score >= 4 and f_score >= 4                 then 'Champions'
        when r_score >= 3 and f_score >= 3                 then 'Loyal'
        when r_score >= 4 and f_score <= 2                 then 'New / Promising'
        when r_score <= 2 and f_score >= 3                 then 'At Risk (was loyal)'
        when r_score <= 2 and f_score <= 2 and m_score >= 4 then 'Cannot Lose (big spend, lapsed)'
        when r_score <= 2                                  then 'Hibernating'
        else 'Needs Attention' end as segment
    from scored
)
select segment, count(*) as customers, round(avg(recency_days)) as avg_recency_days,
       round(avg(frequency), 2) as avg_orders, round(sum(monetary_cm)) as total_cm,
       round(sum(monetary_cm) / sum(sum(monetary_cm)) over (), 4) as share_of_cm
from seg group by 1 order by total_cm desc;
