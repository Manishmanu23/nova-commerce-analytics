{{ config(indexes=[{'columns': ['order_id'], 'unique': True}, {'columns': ['order_date']}, {'columns': ['customer_id']}]) }}
-- grain: ONE ROW PER ORDER (accumulating snapshot: placed -> paid -> shipped -> delivered / cancelled)
--
-- Governed measure columns (gross_revenue, net_revenue, gross_profit, contribution_margin, ...) are
-- already ZERO for orders that must not count (not completed, test orders, invalid dates).
-- => SUM(net_revenue) is always the governed number; no analyst has to remember the filters.
-- The unfiltered "raw" amounts are kept with an _inr suffix for reconciliation and audits.
with o as (select * from {{ ref('int_orders__enriched') }}),
it as (
    select order_id, sum(gross_revenue_inr) as items_gross_inr, sum(return_refund_inr) as return_refund_inr,
           sum(cogs_inr) as cogs_inr, sum(cogs_recovered_inr) as cogs_recovered_inr,
           bool_or(is_orphan_product) as has_orphan_product, bool_or(is_cost_imputed) as has_imputed_cost
    from {{ ref('int_order_items__priced') }} group by 1
),
cr as (
    select order_id, sum(refund_amount_inr) filter (where refund_status = 'processed') as cancellation_refund_inr
    from {{ ref('stg_refunds') }} where is_cancellation_refund group by 1
),
c as (select customer_id, customer_version_key, valid_from, valid_to from {{ ref('int_customers__scd2') }}),
j as (
    select
        o.*, coalesce(c.customer_version_key, 'unknown') as customer_version_key,
        coalesce(it.items_gross_inr, 0) as items_gross_revenue_inr,
        coalesce(it.return_refund_inr, 0) as return_refund_inr_raw,
        coalesce(it.cogs_inr, 0) as cogs_inr_raw, coalesce(it.cogs_recovered_inr, 0) as cogs_recovered_inr_raw,
        coalesce(it.has_orphan_product, false) as has_orphan_product,
        coalesce(it.has_imputed_cost, false) as has_imputed_cost,
        coalesce(cr.cancellation_refund_inr, 0) as cancellation_refund_inr,
        (o.is_completed and o.is_reportable) as is_countable
    from o
    left join it using (order_id)
    left join cr using (order_id)
    left join c on c.customer_id = o.customer_id and o.order_at >= c.valid_from and o.order_at < c.valid_to
)
select
    order_id,
    to_char(order_date, 'YYYYMMDD')::int                         as order_date_key,
    order_date, order_at, date_trunc('month', order_at)::date     as order_month,
    customer_id, customer_version_key, coalesce(geo_id, '-1') as geo_id,
    attributed_channel, campaign_id, session_id, coalesce(device_type, 'unknown') as device_type, os, app_version,
    payment_method, is_prepaid, order_channel, source_system, order_status, coupon_code,
    -- flags
    is_completed, is_cancelled, is_payment_failed, is_reportable, is_countable, is_valid_order_date,
    is_internal_test, is_guest, is_orphan_customer, is_legacy_customer, is_bulk_order, is_member_order, is_first_order,
    customer_order_number, has_orphan_product, has_imputed_cost, source_row_count,
    case when is_first_order then 'new'
         when customer_order_number >= 1 then 'returning'      -- includes legacy customers' orders
         else 'n/a' end                                           as customer_type,
    -- payment funnel
    prepaid_attempts, failed_payment_attempts, success_attempt_no, collected_inr,
    -- raw amounts (unfiltered)
    items_gross_revenue_inr, coupon_discount_inr, shipping_fee_inr, order_total_inr, shipping_cost_inr,
    marketplace_commission_inr, payment_fee_inr, return_refund_inr_raw, cancellation_refund_inr,
    cogs_inr_raw, cogs_recovered_inr_raw,
    -- ===== governed measures (0 when not countable) =====
    case when is_countable then 1 else 0 end                                         as completed_orders,
    case when is_countable then items_gross_revenue_inr else 0 end                   as gross_revenue,
    case when is_countable then coupon_discount_inr else 0 end                       as coupon_discount,
    case when is_countable then return_refund_inr_raw else 0 end                     as return_refunds,
    case when is_countable then items_gross_revenue_inr - coupon_discount_inr - return_refund_inr_raw
         else 0 end                                                                  as net_revenue,
    case when is_countable then cogs_inr_raw - cogs_recovered_inr_raw else 0 end     as net_cogs,
    case when is_countable then items_gross_revenue_inr - coupon_discount_inr - return_refund_inr_raw
                                - (cogs_inr_raw - cogs_recovered_inr_raw) else 0 end as gross_profit,
    case when is_countable then shipping_fee_inr else 0 end                          as shipping_fee_collected,
    case when is_countable then shipping_cost_inr + payment_fee_inr + marketplace_commission_inr
         else 0 end                                                                  as variable_fulfilment_cost,
    case when is_countable then items_gross_revenue_inr - coupon_discount_inr - return_refund_inr_raw
                                - (cogs_inr_raw - cogs_recovered_inr_raw)
                                + shipping_fee_inr - shipping_cost_inr - payment_fee_inr - marketplace_commission_inr
         else 0 end                                                                  as contribution_margin,
    case when is_countable and not is_bulk_order then 1 else 0 end                   as aov_orders,
    case when is_countable and not is_bulk_order then items_gross_revenue_inr - coupon_discount_inr
         else 0 end                                                                  as aov_order_value,
    -- fulfilment timing
    shipped_at, delivered_at, cancelled_at,
    round((extract(epoch from (shipped_at - order_at)) / 3600)::numeric, 1)           as hours_to_ship,
    case when delivered_at >= order_at
         then round((extract(epoch from (delivered_at - order_at)) / 86400)::numeric, 2) end as days_to_deliver
from j
