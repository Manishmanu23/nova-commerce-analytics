-- grain: one row per order.
-- Resolves the business status of every order (completed? reportable?), attribution, membership,
-- and first-order sequencing. Every downstream revenue number depends on these flags.
with o as (select * from {{ ref('stg_orders') }}),
items as (
    select order_id, max(quantity) as max_qty, sum(quantity * unit_sale_price) as items_gross, count(*) as n_lines
    from {{ ref('stg_order_items') }} group by 1
),
pay as (
    select order_id,
           count(*) filter (where gateway <> 'cod')                          as prepaid_attempts,
           count(*) filter (where gateway <> 'cod' and not is_success)       as failed_attempts,
           min(attempt_no) filter (where is_success)                         as success_attempt_no,
           sum(gateway_fee_inr) filter (where is_success)                    as payment_fee_inr,
           sum(amount_inr) filter (where is_success)                         as collected_inr
    from {{ ref('stg_payments') }} group by 1
),
cust as (
    select customer_id, is_internal_test, signup_campaign_id,
           -- order history before the platform migration (data_start_date) was not migrated, so for
           -- customers who signed up earlier we cannot know which order was really their first.
           signup_at < '{{ var("data_start_date") }}'::date as is_legacy_customer
    from {{ ref('int_customers__scd2') }} where is_current
),
camp as (select campaign_id, channel from {{ ref('stg_marketing_campaigns') }}),
-- membership at order time. A set-based join (not a correlated EXISTS per row) keeps this O(n log n).
member_orders as (
    select distinct o.order_id
    from o
    join {{ ref('stg_subscriptions') }} sb
      on sb.customer_id = o.customer_id and o.order_at >= sb.start_at
     and o.order_at < coalesce(sb.end_at, '{{ var("far_future") }}'::timestamp)
),
base as (
    select
        o.*,
        o.customer_id is null                                         as is_guest,
        o.customer_id is not null and c.customer_id is null           as is_orphan_customer,
        coalesce(c.is_internal_test, false)                           as is_internal_test,
        coalesce(c.is_legacy_customer, false)                         as is_legacy_customer,
        o.order_at >= '{{ var("data_start_date") }}'::date
          and o.order_at < '{{ var("data_end_date") }}'::date + 1     as is_valid_order_date,
        o.order_status in ('delivered', 'shipped', 'processing')      as is_completed,
        o.order_status = 'cancelled'                                  as is_cancelled,
        o.order_status = 'payment_failed'                             as is_payment_failed,
        coalesce(i.max_qty, 0) >= {{ var("bulk_order_qty_threshold") }} as is_bulk_order,
        coalesce(i.items_gross, 0)                                    as items_gross_inr,
        coalesce(i.n_lines, 0)                                        as n_lines,
        coalesce(p.prepaid_attempts, 0)                               as prepaid_attempts,
        coalesce(p.failed_attempts, 0)                                as failed_payment_attempts,
        p.success_attempt_no,
        coalesce(p.payment_fee_inr, 0)                                as payment_fee_inr,
        p.collected_inr,
        s.traffic_channel                                             as session_channel,
        s.app_version, s.browser,
        case when uc.campaign_id is not null then s.utm_campaign end  as session_campaign_id,
        c.signup_campaign_id,
        mo.order_id is not null                                       as is_member_order
    from o
    left join items i using (order_id)
    left join pay p using (order_id)
    left join cust c on c.customer_id = o.customer_id
    left join {{ ref('stg_web_sessions') }} s on s.session_id = o.session_id
    left join camp uc on uc.campaign_id = s.utm_campaign
    left join member_orders mo on mo.order_id = o.order_id
),
flagged as (
    select *, (is_valid_order_date and not is_internal_test) as is_reportable from base
),
seq as (
    select order_id,
           row_number() over (partition by customer_id order by order_at, order_id) as customer_order_number
    from flagged
    where is_completed and is_reportable and customer_id is not null and not is_orphan_customer
)
select
    f.*,
    q.customer_order_number,
    -- a "new customer" order: first order in our data AND the customer's history is complete
    coalesce(q.customer_order_number = 1 and not f.is_legacy_customer, false) as is_first_order,
    -- attribution: session UTM (last non-direct touch) > signup campaign for first orders
    coalesce(f.session_campaign_id, case when q.customer_order_number = 1 and not f.is_legacy_customer then f.signup_campaign_id end) as campaign_id,
    case when f.order_channel = 'marketplace' then 'marketplace'
         when coalesce(f.session_campaign_id, case when q.customer_order_number = 1 and not f.is_legacy_customer
                                                   then f.signup_campaign_id end) is not null
              then coalesce(cc.channel, 'unknown')
         else coalesce(f.session_channel, 'direct') end as attributed_channel
from flagged f
left join seq q using (order_id)
left join camp cc on cc.campaign_id = coalesce(f.session_campaign_id,
                                               case when q.customer_order_number = 1 and not f.is_legacy_customer
                                                    then f.signup_campaign_id end)
