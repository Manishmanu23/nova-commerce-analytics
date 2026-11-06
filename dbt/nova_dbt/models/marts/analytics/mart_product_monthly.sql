-- grain: ONE ROW PER (MONTH, PRODUCT). Product & brand profitability and quality.
select order_month as month, product_id, category, subcategory, brand,
       sum(units) as units, sum(gross_revenue) as gross_revenue, sum(markdown) as markdown,
       sum(allocated_coupon) as coupon, sum(return_refunds) as return_refunds, sum(net_revenue) as net_revenue,
       sum(net_cogs) as net_cogs, sum(gross_profit) as gross_profit,
       count(*) filter (where is_countable) as order_lines,
       count(*) filter (where is_countable and is_refunded) as refunded_lines,
       count(*) filter (where is_countable and refund_reason = 'defective') as defective_lines
from {{ ref('fct_order_items') }}
where order_date between '{{ var("data_start_date") }}' and '{{ var("data_end_date") }}'
group by 1, 2, 3, 4, 5
