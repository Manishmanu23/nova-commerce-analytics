/* =====================================================================================
Q13  Refund-rate trend by brand (quarterly) and rank movement
-------------------------------------------------------------------------------------
BUSINESS QUESTION  Is any brand's quality deteriorating?
WHY IT WORKS       Value-based refund rate by ORDER quarter; LAG over each brand's quarters gives the change;
                   RANK within quarter shows relative position.
WHY ORDER DATE     Refunds lag orders by 1-3 weeks. Attributing refunds to ORDER date measures product quality
                   of what we sold; refund-date basis measures cash outflow. Different questions.
CAVEAT             The latest quarter is immature (late-arriving refunds) - its rate is a lower bound.
===================================================================================== */
with b as (
    select date_trunc('quarter', month)::date as quarter, brand, category,
           sum(return_refunds) / nullif(sum(gross_revenue), 0) as refund_rate, sum(gross_revenue) as gross_revenue,
           sum(defective_lines)::numeric / nullif(sum(order_lines), 0) as defective_line_rate
    from marts.mart_product_monthly where category = 'Electronics'
    group by 1, 2, 3
)
select quarter, brand, round(refund_rate, 4) as refund_rate, round(defective_line_rate, 4) as defective_line_rate,
       round(refund_rate - lag(refund_rate) over (partition by brand order by quarter), 4) as change_vs_prev_q,
       rank() over (partition by quarter order by refund_rate desc) as rank_worst_first
from b order by brand, quarter;
