/* =====================================================================================
Q02  Gross revenue -> Contribution margin after marketing waterfall (by quarter)
-------------------------------------------------------------------------------------
BUSINESS QUESTION  Where does each rupee of gross revenue leak before it becomes profit?
WHY IT WORKS       Each step is a governed additive component; the waterfall is just an ordered unpivot.
WHY THIS WAY       CROSS JOIN LATERAL (VALUES …) unpivots in one pass (vs 8 UNION ALLs = 8 scans).
                   Marketing spend is joined at QUARTER grain (not order grain) - spend cannot be
                   allocated to individual orders without an attribution model.
PERFORMANCE        Two aggregations + 8x row expansion of ~8 rows. Trivial.
AT SCALE           Same query on metrics_daily (730 rows) instead of fct_orders.
===================================================================================== */
with q as (
    select date_trunc('quarter', date_day)::date as quarter,
           sum(gross_revenue) gross, sum(coupon_discount) coupons, sum(return_refund_amount) refunds,
           sum(net_revenue) net, sum(net_cogs) cogs, sum(gross_profit) gp, sum(shipping_fee_collected) ship_fee,
           sum(variable_fulfilment_cost) var_cost, sum(contribution_margin) cm, sum(marketing_spend) mkt,
           sum(contribution_margin_after_marketing) cm_after_mkt
    from metrics.metrics_daily group by 1
)
select q.quarter, s.step_order, s.step, s.amount, round(s.amount / nullif(q.gross, 0), 4) as pct_of_gross
from q
cross join lateral (values
    (1, 'Gross revenue',              q.gross),
    (2, '(-) Coupon discounts',       -q.coupons),
    (3, '(-) Return refunds',         -q.refunds),
    (4, '= Net revenue',              q.net),
    (5, '(-) Net COGS',               -q.cogs),
    (6, '= Gross profit',             q.gp),
    (7, '(+) Shipping fees collected', q.ship_fee),
    (8, '(-) Shipping, payment fees, marketplace commission', -q.var_cost),
    (9, '= Contribution margin',      q.cm),
    (10, '(-) Marketing spend',       -q.mkt),
    (11, '= CM after marketing',      q.cm_after_mkt)
) s(step_order, step, amount)
order by q.quarter, s.step_order;
