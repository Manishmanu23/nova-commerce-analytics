/* =====================================================================================
Q17  First-order discount depth vs subsequent behaviour
-------------------------------------------------------------------------------------
BUSINESS QUESTION  Do deeper welcome discounts buy loyalty, or just one cheap order?
WHY IT WORKS       Bucket the first-order coupon as % of first-order gross; compare mature-cohort outcomes.
CAUTION            Observational. Discount depth is confounded with campaign/channel/season. Use this to
                   prioritise an EXPERIMENT (randomised discount levels), not to conclude causality.
===================================================================================== */
select case when first_order_coupon = 0 then '0 none'
            when first_order_coupon / nullif(first_order_gross, 0) < 0.15 then '1 <15%'
            when first_order_coupon / nullif(first_order_gross, 0) < 0.30 then '2 15-30%'
            else '3 30%+' end as first_order_discount_band,
       count(*) filter (where is_mature_90d) as mature_customers,
       round(avg(case when repeated_within_90d then 1.0 else 0 end) filter (where is_mature_90d), 4) as repeat_rate_90d,
       round(avg(cm_90d) filter (where is_mature_90d)) as avg_cm_90d
from marts.mart_customer_ltv
group by 1 order by 1;
