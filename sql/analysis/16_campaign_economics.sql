/* =====================================================================================
Q16  Campaign economics: spend, CAC, first-order discount cost, 90-day CM per customer, payback
-------------------------------------------------------------------------------------
BUSINESS QUESTION  Which campaigns bought growth that is worth having?
WHY IT WORKS       Customers are linked to the campaign that acquired them (signup_campaign_id);
                   spend is summed at campaign grain; outcomes come from mature 90-day windows only.
WHY THIS WAY       A campaign can look great on CAC (cheap customers) and ROAS (big first basket) and still
                   destroy value if those customers never return. CM-based 90d payback exposes that.
===================================================================================== */
with spend as (
    select campaign_id, sum(spend_inr) as spend from marts.fct_marketing_spend group by 1
),
cust as (
    select signup_campaign_id as campaign_id, count(*) as customers,
           count(*) filter (where is_mature_90d) as mature_90d,
           avg(cm_90d) filter (where is_mature_90d) as cm_90d_per_customer,
           avg(first_order_coupon) as avg_first_order_coupon,
           avg(case when repeated_within_90d then 1.0 else 0 end) filter (where is_mature_90d) as repeat_rate_90d
    from marts.mart_customer_ltv where signup_campaign_id is not null group by 1
)
select c.campaign_id, dc.campaign_name, dc.channel, dc.first_order_discount_pct, c.customers,
       round(s.spend) as spend, round(s.spend / nullif(c.customers, 0)) as cac,
       round(c.avg_first_order_coupon) as avg_first_order_coupon,
       round(c.cm_90d_per_customer) as cm_90d_per_customer,
       round(c.repeat_rate_90d, 3) as repeat_rate_90d,
       round(c.cm_90d_per_customer / nullif(s.spend / nullif(c.customers, 0), 0), 2) as cm90_payback_ratio
from cust c
join marts.dim_campaign dc using (campaign_id)
left join spend s using (campaign_id)
where c.customers >= 30
order by cm90_payback_ratio nulls last;
