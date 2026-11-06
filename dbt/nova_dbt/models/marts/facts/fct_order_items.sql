-- grain: ONE ROW PER ORDER LINE (order_id x product). Product profitability lives here.
with i as (select * from {{ ref('int_order_items__priced') }}),
o as (select order_id, order_date, order_month, customer_id, geo_id, attributed_channel, device_type,
              is_countable, is_bulk_order, is_first_order from {{ ref('fct_orders') }})
select
    i.order_item_id, i.order_id, o.order_date, o.order_month, o.customer_id, o.geo_id, o.attributed_channel,
    o.device_type, coalesce(i.product_version_key, 'unknown') as product_version_key, i.product_id,
    i.category, i.subcategory, i.brand, i.is_orphan_product, i.is_cost_imputed, o.is_countable, o.is_bulk_order,
    o.is_first_order, i.quantity, i.unit_list_price, i.unit_sale_price, i.unit_cost, i.refund_reason, i.first_refund_at,
    i.return_refund_inr > 0 as is_refunded,
    -- governed measures (0 when order not countable)
    case when o.is_countable then i.quantity else 0 end                                 as units,
    case when o.is_countable then i.list_value_inr else 0 end                           as list_value,
    case when o.is_countable then i.markdown_inr else 0 end                             as markdown,
    case when o.is_countable then i.gross_revenue_inr else 0 end                        as gross_revenue,
    case when o.is_countable then coalesce(i.allocated_coupon_inr, 0) else 0 end        as allocated_coupon,
    case when o.is_countable then i.return_refund_inr else 0 end                        as return_refunds,
    case when o.is_countable then i.gross_revenue_inr - coalesce(i.allocated_coupon_inr, 0) - i.return_refund_inr
         else 0 end                                                                     as net_revenue,
    case when o.is_countable then i.cogs_inr - i.cogs_recovered_inr else 0 end          as net_cogs,
    case when o.is_countable then i.gross_revenue_inr - coalesce(i.allocated_coupon_inr, 0) - i.return_refund_inr
                                  - (i.cogs_inr - i.cogs_recovered_inr) else 0 end      as gross_profit
from i
join o using (order_id)
