-- grain: one row per order line.
-- Joins the product version valid at order time (SCD2), allocates order-level coupons to lines
-- (pro-rata to line value) and attaches processed RETURN refunds (cancellation refunds excluded).
with i as (select * from {{ ref('stg_order_items') }}),
o as (select order_id, order_at, coupon_discount_inr from {{ ref('stg_orders') }}),
p as (select * from {{ ref('int_products__scd2') }}),
r as (
    select order_item_id,
           sum(refund_amount_inr) filter (where refund_status = 'processed') as return_refund_inr,
           min(refund_at)                                                   as first_refund_at,
           (array_agg(refund_reason order by refund_at))[1]                 as refund_reason
    from {{ ref('stg_refunds') }}
    where not is_cancellation_refund
    group by 1
),
priced as (
    select
        i.order_item_id, i.order_id, i.product_id, p.product_version_key,
        coalesce(p.category, 'Unknown') as category, coalesce(p.subcategory, 'Unknown') as subcategory,
        coalesce(p.brand, 'Unknown') as brand, p.product_version_key is null as is_orphan_product,
        i.quantity, i.unit_list_price, i.unit_sale_price,
        coalesce(p.unit_cost, round(i.unit_list_price * 0.6, 2))          as unit_cost,
        (p.unit_cost is null or coalesce(p.is_cost_imputed, false))       as is_cost_imputed,
        i.quantity * i.unit_list_price                                    as list_value_inr,
        i.quantity * i.unit_sale_price                                    as gross_revenue_inr,
        i.quantity * (i.unit_list_price - i.unit_sale_price)              as markdown_inr,
        o.coupon_discount_inr * (i.quantity * i.unit_sale_price)
            / nullif(sum(i.quantity * i.unit_sale_price) over (partition by i.order_id), 0) as allocated_coupon_inr,
        coalesce(r.return_refund_inr, 0) as return_refund_inr, r.first_refund_at, r.refund_reason
    from i
    join o using (order_id)
    left join p on p.product_id = i.product_id and o.order_at >= p.valid_from and o.order_at < p.valid_to
    left join r using (order_item_id)
)
select *,
       quantity * unit_cost as cogs_inr,
       -- returned units are restocked (COGS reversed) unless defective; partial refunds are price adjustments
       case when return_refund_inr > 0 and coalesce(refund_reason, '') <> 'defective'
                 and return_refund_inr >= 0.99 * (gross_revenue_inr - coalesce(allocated_coupon_inr, 0))
            then quantity * unit_cost else 0 end as cogs_recovered_inr
from priced
