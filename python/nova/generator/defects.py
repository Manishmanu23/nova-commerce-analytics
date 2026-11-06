"""
Deliberate, documented data defects. Each defect mimics a real production failure mode.
Every function returns the mutated frame and appends to a defect log (-> data/ground_truth/defects.json).
"""
import numpy as np
import pandas as pd

from . import scenarios as S

LOG = []


def _log(table, defect, n, note):
    LOG.append(dict(table=table, defect=defect, rows_affected=int(n), note=note))


def dup_rows(df, rate, rng, table, bump_col=None, note="retry re-sent records"):
    n = int(len(df) * rate)
    d = df.sample(n, random_state=int(rng.integers(1e9))).copy()
    if bump_col:
        d[bump_col] = (pd.to_datetime(d[bump_col]) + pd.to_timedelta(rng.uniform(1, 30, n), unit="h")) \
            .dt.strftime("%Y-%m-%d %H:%M:%S")
    _log(table, "duplicate_rows", n, note)
    return pd.concat([df, d], ignore_index=True)


def messy_labels(df, col, variants: dict, rate, rng, table):
    s = df[col].astype(object).copy()
    hit = 0
    for clean, vs in variants.items():
        m = (s == clean) & (rng.random(len(s)) < rate)
        s[m] = rng.choice(vs, m.sum())
        hit += m.sum()
    df[col] = s
    _log(table, "inconsistent_labels", hit, f"{col}: {list(variants)[:3]}...")
    return df


def null_out(df, col, rate, rng, table, note=""):
    m = rng.random(len(df)) < rate
    df.loc[m, col] = None
    _log(table, "missing_values", m.sum(), f"{col} {note}")
    return df


def apply_all(raw: dict, rng) -> dict:
    LOG.clear()
    # ---- customers
    c = raw["customers"]
    c["email"] = np.where(rng.random(len(c)) < 0.05, "  " + c.email.str.upper() + " ", c.email)
    _log("customers", "unnormalised_email", int(0.05 * len(c)), "upper-case + whitespace")
    c = null_out(c, "geo_id", 0.04, rng, "customers", "(address not captured at signup)")
    c = messy_labels(c, "acquisition_channel", {
        "paid_social": ["Facebook", "Meta Ads", "FB", "paid social"],
        "paid_search": ["Google Ads", "google_cpc", "Paid Search"],
        "organic": ["Organic", "SEO", "organic "]}, 0.25, rng, "customers")
    c = dup_rows(c, 0.02, rng, "customers", note="exact duplicate CDC rows")
    late = rng.choice(c.customer_id.unique(), 60, replace=False)
    c = c[~c.customer_id.isin(late)]
    _log("customers", "late_arriving_dimension", 60, "customers missing from extract -> orphan orders")
    raw["customers"] = c
    # ---- products
    p = raw["products"]
    p = messy_labels(p, "category", {
        "Electronics": ["electronics", " Electronics", "Electronic"],
        "Home & Kitchen": ["Home and Kitchen", "home_kitchen", "HOME & KITCHEN"],
        "Beauty & Personal Care": ["Beauty", "beauty & personal care"],
        "Fashion": ["fashion", "Apparel"]}, 0.2, rng, "products")
    p = null_out(p, "unit_cost", 0.02, rng, "products", "(cost not yet synced from ERP)")
    raw["products"] = p
    # ---- orders & items
    o, oi = raw["orders"], raw["order_items"]
    m = o.source_system == "mkt_feed"
    o.loc[m, "order_status"] = o.loc[m, "order_status"].str.upper()
    _log("orders", "inconsistent_labels", m.sum(), "marketplace feed sends UPPERCASE status")
    o = messy_labels(o, "payment_method", {"UPI": ["upi", "Upi ", "UPI_INTENT"], "Card": ["CARD", "credit_card"],
                                           "COD": ["cod", "Cash on Delivery"]}, 0.1, rng, "orders")
    # S4: full-day batch re-sent
    ist_day = (pd.to_datetime(o.order_ts) + pd.Timedelta(hours=5, minutes=30)).dt.strftime("%Y-%m-%d")
    dmask = ist_day == str(S.S4_DUP_DAY)
    dup_o = o[dmask].copy()
    dup_o["_extracted_at"] = (pd.to_datetime(dup_o._extracted_at) + pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d %H:%M:%S")
    dup_i = oi[oi.order_id.isin(dup_o.order_id)].copy()
    _log("orders", "full_day_duplicate_batch", len(dup_o), f"S4: all orders for {S.S4_DUP_DAY} re-sent")
    o = dup_rows(o, 0.012, rng, "orders", bump_col="_extracted_at", note="OMS retry duplicates (later _extracted_at)")
    o = pd.concat([o, dup_o], ignore_index=True)
    oi = pd.concat([oi, dup_i], ignore_index=True)
    oi = dup_rows(oi, 0.004, rng, "order_items", note="exact duplicate line items")
    # invalid dates
    idx = o.sample(frac=0.0015, random_state=1).index
    o.loc[idx, "order_ts"] = "1970-01-01 00:00:00"
    idx2 = o.sample(frac=0.0005, random_state=2).index
    o.loc[idx2, "order_ts"] = "2031-" + o.loc[idx2, "order_ts"].str[5:]
    dl = o[o.delivered_ts.notna() & (o.delivered_ts != "")].sample(frac=0.002, random_state=3).index
    o.loc[dl, "delivered_ts"] = (pd.to_datetime(o.loc[dl, "order_ts"], errors="coerce") - pd.Timedelta(days=2)) \
        .dt.strftime("%Y-%m-%d %H:%M:%S")
    _log("orders", "invalid_dates", len(idx) + len(idx2) + len(dl), "epoch/future order_ts, delivered before ordered")
    # orphan product ids
    k = oi.sample(frac=0.002, random_state=4).index
    oi.loc[k, "product_id"] = "PRD-9" + pd.Series(rng.integers(1000, 9999, len(k)), index=k).astype(str)
    _log("order_items", "referential_integrity", len(k), "product_id not in product master")
    raw["orders"], raw["order_items"] = o, oi
    # ---- payments
    pay = raw["payments"]
    mk = pay.gateway == "mkt_settlement"
    pay.loc[mk, "amount"] = (pay.loc[mk, "amount"].astype(float) * 100).round(0)
    _log("payments", "unit_mismatch", mk.sum(), "marketplace settlement feed reports amount in paise")
    pay = messy_labels(pay, "payment_method", {"UPI": ["upi", "UPI_INTENT"], "Card": ["CARD", "debit_card"]},
                       0.1, rng, "payments")
    n = int(len(pay) * 0.003)
    d = pay[pay.status == "success"].sample(n, random_state=5).copy()
    d["payment_id"] = ["PAY-D" + str(x).zfill(7) for x in range(n)]
    _log("payments", "duplicate_transactions", n, "same gateway_txn_ref, new payment_id (webhook replay)")
    raw["payments"] = pd.concat([pay, d], ignore_index=True)
    # ---- refunds
    r = raw["refunds"]
    neg = rng.random(len(r)) < 0.01
    r.loc[neg, "refund_amount"] = -r.loc[neg, "refund_amount"].astype(float)
    _log("refunds", "negative_values", neg.sum(), "sign convention differs in one source")
    r = dup_rows(r, 0.005, rng, "refunds")
    raw["refunds"] = r
    # ---- marketing
    mc = raw["marketing_campaigns"]
    mc = messy_labels(mc, "channel", {"paid_social": ["Meta", "facebook", "FB"],
                                      "paid_search": ["Google", "google_ads"]}, 0.4, rng, "marketing_campaigns")
    raw["marketing_campaigns"] = mc
    ms = raw["marketing_spend"]
    ms = null_out(ms, "impressions", 0.01, rng, "marketing_spend", "(API returned null)")
    adj = ms.sample(6, random_state=6).copy()
    adj["spend_inr"] = -np.round(adj.spend_inr.astype(float) * 0.2, 2)
    adj["impressions"], adj["clicks"] = 0, 0
    _log("marketing_spend", "negative_values", 6, "LEGIT: platform credit notes (negative spend) - do not drop")
    raw["marketing_spend"] = pd.concat([ms, adj], ignore_index=True)
    # ---- support
    t = raw["customer_support"]
    t = messy_labels(t, "category", {"payment_issue": ["Payment Issue", "payments"],
                                     "return_refund": ["Refund", "return/refund"]}, 0.15, rng, "customer_support")
    bad = t[t.resolved_ts.notna() & (t.resolved_ts != "")].sample(frac=0.003, random_state=7).index
    t.loc[bad, "resolved_ts"] = (pd.to_datetime(t.loc[bad, "created_ts"]) - pd.Timedelta(hours=3)) \
        .dt.strftime("%Y-%m-%d %H:%M:%S")
    _log("customer_support", "invalid_dates", len(bad), "resolved before created")
    raw["customer_support"] = t
    _log("web_sessions", "bot_traffic", 0, f"~20k headless sessions on {S.DQ_BOT_SPIKE_DAY}")
    return raw
