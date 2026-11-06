// Parameters: PgServer (text, e.g. "localhost:5432"), PgDatabase (text, "nova")
// Example query for one table - duplicate per table and change schema/item.
let
    Source   = PostgreSQL.Database(PgServer, PgDatabase),
    Orders   = Source{[Schema = "marts", Item = "fct_orders"]}[Data],
    // keep only what the report uses (smaller model, faster refresh)
    Keep     = Table.SelectColumns(Orders, {
                 "order_id","order_date","customer_version_key","geo_id","attributed_channel","campaign_id",
                 "device_type","payment_method","order_channel","customer_type","is_countable","is_first_order",
                 "is_member_order","is_bulk_order","completed_orders","gross_revenue","coupon_discount",
                 "return_refunds","net_revenue","net_cogs","gross_profit","shipping_fee_collected",
                 "variable_fulfilment_cost","contribution_margin","aov_orders","aov_order_value"}),
    Typed    = Table.TransformColumnTypes(Keep, {{"order_date", type date}})
in
    Typed
