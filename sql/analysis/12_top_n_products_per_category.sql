/* =====================================================================================
Q12  Top-5 products by gross profit within each category (2025), with ties handled
-------------------------------------------------------------------------------------
BUSINESS QUESTION  Which products actually make money in each category (not just sell)?
WHY IT WORKS       DENSE_RANK() partitioned by category; filter rank <= 5 in an outer query
                   (window functions cannot be used in WHERE of the same SELECT).
WHY DENSE_RANK     ROW_NUMBER would drop tied products arbitrarily; RANK would leave gaps (1,1,3).
                   Choose based on the business rule and SAY which you chose.
AT SCALE           Pre-aggregate to product-month (mart_product_monthly) before ranking: rank 500 rows, not 50M.
===================================================================================== */
with p as (
    select category, product_id, brand, sum(gross_profit) as gross_profit, sum(net_revenue) as net_revenue,
           sum(return_refunds) / nullif(sum(gross_revenue), 0) as refund_rate
    from marts.mart_product_monthly
    where month >= '2025-01-01'
    group by 1, 2, 3
),
r as (select *, dense_rank() over (partition by category order by gross_profit desc) as rnk from p)
select category, rnk, product_id, brand, round(gross_profit) as gross_profit, round(net_revenue) as net_revenue,
       round(refund_rate, 4) as refund_rate
from r where rnk <= 5
order by category, rnk;
