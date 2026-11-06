{{ config(severity='warn') }}
-- Finance reconciliation: money collected by the gateway should equal the order total for completed
-- prepaid orders. Fails loudly if the paise->rupee conversion or txn de-dup regresses.
select order_id, order_total_inr, collected_inr
from {{ ref('fct_orders') }}
where is_countable and is_prepaid and collected_inr is not null
  and abs(collected_inr - order_total_inr) > 1
