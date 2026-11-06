"""Generate docs/04_data_dictionary.md from the live warehouse + dbt YAML descriptions (docs never drift from code)."""
from pathlib import Path

import yaml

from nova.common.db import read_sql
from nova.common.report import ROOT

SCHEMAS = ["marts", "metrics"]
# fallback descriptions for columns that recur across models (model YAML wins when present)
COMMON = {
    "order_id": "Natural key of the order (OMS).", "order_item_id": "Natural key of the order line.",
    "customer_id": "Natural key of the customer (CRM). NULL = guest checkout.",
    "customer_version_key": "FK to dim_customer version valid at event time (SCD2).",
    "product_version_key": "FK to dim_product version valid at order time (SCD2).",
    "product_id": "Natural key of the product.", "geo_id": "FK to dim_geography ('-1' = Unknown).",
    "campaign_id": "FK to dim_campaign; attributed campaign (session UTM, else signup campaign on first order).",
    "session_id": "Web/app session id (NULL for marketplace orders).",
    "order_date": "Order date in IST.", "order_at": "Order timestamp in IST (source is UTC).",
    "order_month": "First day of the order month (IST).", "date_day": "Calendar date (IST).",
    "month": "First day of the month.", "cohort_month": "Month of the customer's first completed order.",
    "attributed_channel": "Standardised channel after attribution (dim_channel).",
    "device_type": "mobile_app | mobile_web | desktop | unknown (marketplace).",
    "payment_method": "Standardised payment method (UPI, Card, COD, Wallet, EMI).",
    "is_countable": "TRUE when the order is completed AND reportable - governed measures are non-zero only then.",
    "is_completed": "Order status in delivered/shipped/processing.", "is_reportable": "Valid order date and not an internal test order.",
    "is_bulk_order": "Any line with quantity >= 20 (B2B). Kept in revenue, excluded from AOV.",
    "is_first_order": "First completed order of a non-legacy customer (= new customer).",
    "is_legacy_customer": "Signed up before 2024; pre-2024 history not migrated, excluded from cohort/LTV analysis.",
    "is_member_order": "Nova Plus membership active at order time.", "is_bot": "Session flagged as bot traffic.",
    "gross_revenue": "Governed: qty x selling price on countable orders (after markdowns, before coupons/refunds).",
    "net_revenue": "Governed: gross revenue - coupon discounts - processed return refunds.",
    "gross_profit": "Governed: net revenue - net COGS.", "net_cogs": "COGS minus cost recovered on restockable returns.",
    "contribution_margin": "Governed: gross profit + shipping fees - shipping cost - payment fees - marketplace commission.",
    "contribution_margin_after_marketing": "Contribution margin minus net marketing spend (date/channel grain only).",
    "coupon_discount": "Order-level coupon discount on countable orders.", "return_refunds": "Processed return refunds on countable orders.",
    "completed_orders": "1 if the order is countable, else 0.", "orders": "Count of countable orders.",
    "aov_orders": "AOV denominator: countable non-bulk orders.", "aov_order_value": "AOV numerator: gross - coupons on countable non-bulk orders.",
    "aov": "Average order value = aov_order_value / aov_orders.",
    "sessions": "Non-bot web/app sessions.", "purchase_sessions": "Non-bot sessions with a purchase event.",
    "checkout_sessions": "Non-bot sessions that began checkout.", "payment_attempts": "Prepaid payment attempts (COD excluded).",
    "successful_payment_attempts": "Successful prepaid payment attempts.", "marketing_spend": "Net marketing spend (credit notes netted).",
    "acquisition_spend": "Net spend of acquisition-objective campaigns (excludes email/CRM).",
    "new_customers": "Customers whose first completed order falls in the period.",
    "paid_new_customers": "New customers whose first order is attributed to a paid campaign.",
    "conversion_rate": "purchase_sessions / sessions.", "payment_success_rate": "successful_payment_attempts / payment_attempts.",
    "refund_rate": "return refunds / gross revenue (order-date basis).", "cm_pct": "contribution margin / net revenue.",
    "cac": "acquisition_spend / paid_new_customers.", "roas": "attributed net revenue / marketing spend.",
    "valid_from": "SCD2 validity start (inclusive).", "valid_to": "SCD2 validity end (exclusive).",
    "is_current": "TRUE for the current SCD2 version.", "dimension_name": "Dimension of the breakdown row.",
    "dimension_value": "Value of the dimension.", "months_since_first": "Months since the customer's first order month.",
    "is_active": "Customer placed >= 1 countable order in the month.",
}


def yaml_docs():
    docs = {}
    for p in (ROOT / "dbt" / "nova_dbt" / "models").rglob("*.yml"):
        y = yaml.safe_load(p.read_text()) or {}
        for m in y.get("models", []):
            docs[m["name"]] = (m.get("description", ""), {c["name"]: c.get("description", "")
                                                          for c in m.get("columns", [])})
    return docs


def first_comment_lines(model):
    p = next((ROOT / "dbt" / "nova_dbt" / "models").rglob(f"{model}.sql"), None)
    if not p:
        return ""
    lines = [ln[2:].strip() for ln in p.read_text().splitlines() if ln.startswith("--")][:3]
    return " ".join(lines)


def main():
    cols = read_sql("""select table_schema, table_name, column_name, data_type, ordinal_position
                       from information_schema.columns where table_schema in ('marts','metrics')
                       order by table_schema, table_name, ordinal_position""")
    docs = yaml_docs()
    out = ["# Data Dictionary", "",
           "Generated from the warehouse (`information_schema`) plus dbt model YAML, by "
           "`python -m nova.common.data_dictionary`. Grain statements are in the first line of each model.", ""]
    for (sch, tbl), g in cols.groupby(["table_schema", "table_name"], sort=False):
        desc, cdesc = docs.get(tbl, ("", {}))
        out += [f"## `{sch}.{tbl}`", "", (desc or first_comment_lines(tbl)).strip(), "",
                "| column | type | description |", "|---|---|---|"]
        for r in g.itertuples():
            out.append(f"| {r.column_name} | {r.data_type} | {cdesc.get(r.column_name) or COMMON.get(r.column_name, '')} |")
        out.append("")
    Path(ROOT / "docs" / "04_data_dictionary.md").write_text("\n".join(out))
    print("wrote docs/04_data_dictionary.md", len(cols), "columns")


if __name__ == "__main__":
    main()
