/* =====================================================================================
Q25  Pareto: what share of contribution margin comes from the top X% of customers?
-------------------------------------------------------------------------------------
BUSINESS QUESTION  How concentrated is profit? (Risk + where to focus retention spend.)
WHY IT WORKS       Running SUM ordered by CM desc / total; PERCENT_RANK gives the customer percentile.
NOTE               Some customers have NEGATIVE lifetime CM (heavy discounts + returns) - they appear at the
                   bottom and pull the curve above 100% before it comes back. That's a finding, not a bug.
===================================================================================== */
with c as (select customer_id, total_cm from marts.mart_customer_ltv),
r as (
    select customer_id, total_cm,
           percent_rank() over (order by total_cm desc) as pct_rank,
           sum(total_cm) over (order by total_cm desc rows between unbounded preceding and current row)
             / sum(total_cm) over () as cum_share
    from c
)
select b.bucket as top_pct_of_customers, round(max(r.cum_share), 4) as share_of_total_cm
from (values (0.01), (0.05), (0.10), (0.20), (0.50), (1.0)) b(bucket)
join r on r.pct_rank <= b.bucket
group by 1 order by 1;
