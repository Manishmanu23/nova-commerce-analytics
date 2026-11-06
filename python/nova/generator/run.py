"""
Generate the NovaCommerce source extracts.

    python -m nova.generator.run --customers 30000 --out data/landing
    python -m nova.generator.run --customers 1500 --session-mult 0.1 --out data/sample/landing   # CI sample

Output: data/landing/<batch_date>/<table>.csv  (+ data/ground_truth/*.json, never read by analysis code)
"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from . import defects
from . import scenarios as S
from .calendar import dates_table
from .commerce import CommerceSim
from .config import GenConfig
from .reference import CHANNEL_CAC, CHANNEL_CODE, campaigns, geography, products
from .web import build_sessions

DOMAINS = ["gmail.com", "yahoo.co.in", "outlook.com", "rediffmail.com", "hotmail.com"]


def ts_str(base, arr, utc=True):
    """float days-since-start (IST) -> 'YYYY-MM-DD HH:MM:SS' string (UTC by default). NaN -> ''."""
    arr = np.asarray(arr, dtype=float)
    out = np.full(arr.shape, "", dtype=object)
    m = np.isfinite(arr)
    secs = np.round((arr[m] - (5.5 / 24 if utc else 0)) * 86400).astype("int64")
    dt = pd.to_datetime(pd.Timestamp(base).value + secs * 1_000_000_000)
    out[m] = dt.strftime("%Y-%m-%d %H:%M:%S").values
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--customers", type=int, default=GenConfig.n_customers)
    ap.add_argument("--session-mult", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="data/landing")
    a = ap.parse_args(argv)
    cfg = replace(GenConfig(), n_customers=a.customers, session_multiplier=a.session_mult, seed=a.seed)
    rng = np.random.default_rng(cfg.seed)
    t0 = time.time()
    base = pd.Timestamp(cfg.start)
    X = (cfg.extraction_date - cfg.start).days + 2 / 24          # extraction instant (days offset)

    geo = geography()
    prods = products(rng, cfg.n_products_per_category)
    camps = campaigns(cfg.start, cfg.end)
    sim = CommerceSim(cfg, rng, geo, prods, camps)
    C = sim.make_customers()
    sim.run()
    print(f"simulated {len(sim.orders):,} orders in {time.time() - t0:.1f}s")
    sess, ev, idmap = build_sessions(sim, cfg, rng)
    print(f"sessions {len(sess):,} events {len(ev):,}  ({time.time() - t0:.1f}s)")

    raw = {}
    # ---------------- customers (CDC-style: one row per version)
    cid_num = np.arange(1, len(C) + 1)
    email = np.array([f"user{n}.{rng.integers(10, 99)}@{DOMAINS[n % 5]}" for n in cid_num], dtype=object)
    email[C.is_test.values] = [f"qa.tester{j}@novacommerce.test" for j in range(C.is_test.sum())]
    v1 = pd.DataFrame({"customer_id": C.customer_id, "email": email, "signup_ts": ts_str(base, C.signup_t),
                       "geo_id": geo.geo_id.values[C.geo1], "acquisition_channel": C.acq,
                       "signup_campaign_id": C.campaign_id, "marketing_opt_in": C.opt_in,
                       "updated_at": ts_str(base, C.signup_t)})
    mv = C[C.moves & (C.move_t < sim.T)]
    v2 = v1.loc[mv.index].copy()
    v2["geo_id"] = geo.geo_id.values[mv.geo2]
    v2["updated_at"] = ts_str(base, mv.move_t)
    cust = pd.concat([v1, v2], ignore_index=True).sort_values(["customer_id", "updated_at"])
    cust["_extracted_at"] = cust.updated_at
    raw["customers"] = cust

    # ---------------- products (one row per version)
    p1 = prods.drop(columns=["popularity"]).copy()
    p1["updated_at"] = "2023-06-01 00:00:00"
    p2 = p1[sim.p_v2].copy()
    p2["list_price"], p2["unit_cost"] = sim.p_price2[sim.p_v2], sim.p_cost2[sim.p_v2]
    p2["valid_from"], p2["updated_at"] = "2025-04-01", "2025-04-01 00:00:00"
    P = pd.concat([p1, p2], ignore_index=True).drop(columns=["valid_from"])
    P["_extracted_at"] = P.updated_at
    raw["products"] = P

    # ---------------- orders
    Ord = pd.DataFrame(sim.orders, columns=["order_id", "customer_id", "t", "order_channel", "device_type", "os",
                                          "geo_id", "payment_method", "coupon_code", "subtotal_inr",
                                          "coupon_discount_inr", "shipping_fee_inr", "order_total_inr",
                                          "shipping_cost_inr", "marketplace_commission_inr", "order_status",
                                          "ship_t", "deliv_t", "canc_t", "is_first", "cidx", "s2"])
    Ord["session_id"] = Ord.order_id.map({k: idmap[v] for k, v in sim.order_session.items()}).astype("Int64")
    last = np.nanmax(np.vstack([Ord.t, Ord.ship_t, Ord.deliv_t, Ord.canc_t]), axis=0)
    ext = np.minimum(last + rng.uniform(1, 26, len(Ord)) / 24, X)
    orders = pd.DataFrame({
        "order_id": Ord.order_id, "customer_id": Ord.customer_id, "session_id": Ord.session_id,
        "order_ts": ts_str(base, Ord.t), "order_channel": Ord.order_channel, "device_type": Ord.device_type,
        "os": Ord.os, "geo_id": Ord.geo_id, "payment_method": Ord.payment_method, "coupon_code": Ord.coupon_code,
        "subtotal_inr": Ord.subtotal_inr, "coupon_discount_inr": Ord.coupon_discount_inr,
        "shipping_fee_inr": Ord.shipping_fee_inr, "order_total_inr": Ord.order_total_inr,
        "shipping_cost_inr": Ord.shipping_cost_inr, "marketplace_commission_inr": Ord.marketplace_commission_inr,
        "order_status": Ord.order_status, "shipped_ts": ts_str(base, Ord.ship_t),
        "delivered_ts": ts_str(base, Ord.deliv_t), "cancelled_ts": ts_str(base, Ord.canc_t),
        "source_system": Ord.order_channel.map({"app": "app_oms", "web": "web_oms", "marketplace": "mkt_feed"}),
        "_extracted_at": ts_str(base, ext)})
    raw["orders"] = orders
    ext_map = dict(zip(orders.order_id, orders._extracted_at))
    Itm = pd.DataFrame(sim.items, columns=["order_item_id", "order_id", "product_id", "quantity",
                                         "unit_list_price", "unit_sale_price"])
    Itm["_extracted_at"] = Itm.order_id.map(ext_map)
    raw["order_items"] = Itm

    # ---------------- payments
    Y = pd.DataFrame(sim.payments, columns=["payment_id", "order_id", "attempt_no", "t", "payment_method",
                                            "gateway", "amount", "status", "failure_reason", "gateway_txn_ref",
                                            "gateway_fee_inr"])
    Y = Y[Y.t <= X]
    raw["payments"] = pd.DataFrame({
        "payment_id": Y.payment_id, "order_id": Y.order_id, "attempt_no": Y.attempt_no,
        "payment_ts": ts_str(base, Y.t), "payment_method": Y.payment_method, "gateway": Y.gateway,
        "amount": Y.amount, "status": Y.status, "failure_reason": Y.failure_reason,
        "gateway_txn_ref": Y.gateway_txn_ref, "gateway_fee_inr": Y.gateway_fee_inr,
        "_extracted_at": ts_str(base, np.minimum(Y.t + rng.uniform(0.01, 2, len(Y)) / 24, X))})

    # ---------------- refunds
    R = pd.DataFrame(sim.refunds, columns=["refund_id", "order_id", "order_item_id", "t", "refund_amount",
                                           "refund_reason", "refund_status", "ext"])
    raw["refunds"] = pd.DataFrame({
        "refund_id": R.refund_id, "order_id": R.order_id, "order_item_id": R.order_item_id,
        "refund_ts": ts_str(base, R.t), "refund_amount": R.refund_amount, "refund_reason": R.refund_reason,
        "refund_status": R.refund_status, "_extracted_at": ts_str(base, R.ext), "_ext_t": R.ext})

    # ---------------- subscriptions
    SB = pd.DataFrame(sim.subs)
    SB = SB[SB.start_t < sim.T].reset_index(drop=True)
    raw["subscriptions"] = pd.DataFrame({
        "subscription_id": [f"SUB-{i + 1:06d}" for i in range(len(SB))], "customer_id": SB.customer_id,
        "plan_type": SB.plan_type, "start_ts": ts_str(base, SB.start_t), "end_ts": ts_str(base, SB.end_t),
        "status": np.where(SB.end_t.isna(), "active", "cancelled"), "fee_inr": SB.fee,
        "_extracted_at": ts_str(base, np.where(SB.end_t.isna(), SB.start_t, SB.end_t) + 0.1)})

    # ---------------- marketing
    mc = camps.copy()
    mc["start_date"], mc["end_date"] = mc.start_date.astype(str), mc.end_date.astype(str)
    raw["marketing_campaigns"] = mc
    buyers = C[C.is_buyer & (C.first_t < sim.T) & (C.campaign_id != "")]
    acq = buyers.assign(day=buyers.signup_t.astype(int)).groupby(["campaign_id", "day"]).size()
    cpc = {"paid_search": 18, "paid_social": 9, "affiliate": 12, "marketplace": 7, "email": 0.6}
    ctr = {"paid_search": 0.04, "paid_social": 0.012, "affiliate": 0.02, "marketplace": 0.03, "email": 0.15}
    floor = {"paid_search": 600, "paid_social": 500, "affiliate": 150, "marketplace": 300, "email": 300}
    rows = []
    for r in camps.itertuples():
        s, e = sim.off(r.start_date), min(sim.off(r.end_date), sim.T - 1)
        cac = 300 if r.campaign_id == S.S1_CAMPAIGN_ID else CHANNEL_CAC.get(r.channel, 0) * (
            1.2 if "FEST" in r.campaign_id else 1.0)
        for d in range(s, e + 1):
            n_new = acq.get((r.campaign_id, d), 0)
            spend = (cac * n_new + floor[r.channel] * sim.demand[d] * cfg.n_customers / 30000) * rng.lognormal(0, 0.2)
            clicks = int(spend / cpc[r.channel] * rng.lognormal(0, 0.1))
            rows.append((str(sim.days[d].date()), r.campaign_id, CHANNEL_CODE[r.channel],
                         int(clicks / ctr[r.channel]), clicks, round(spend, 2)))
    raw["marketing_spend"] = pd.DataFrame(rows, columns=["spend_date", "campaign_id", "platform_code",
                                                         "impressions", "clicks", "spend_inr"])

    # ---------------- web
    raw["web_sessions"] = pd.DataFrame({
        "session_id": sess.session_id.values, "customer_id": sess.customer_id.values,
        "session_start_ts": ts_str(base, sess.start_t.values), "device_type": sess.device.values,
        "os": sess.os.values, "browser": sess.browser.values, "app_version": sess.app_version.values,
        "geo_id": sess.geo_id.values, "traffic_channel": sess.traffic.values, "utm_campaign": sess.utm.values,
        "landing_page": sess.landing_page.values, "duration_sec": sess.duration_sec.values})
    raw["funnel_events"] = pd.DataFrame({
        "event_id": ev.event_id.values, "session_id": ev.session_id.values,
        "event_ts": ts_str(base, ev.ts.values), "event_name": ev.event_name.values,
        "product_id": ev.product_id.values})

    # ---------------- support
    TK = pd.DataFrame(sim.tickets, columns=["ticket_id", "customer_id", "order_id", "t", "category",
                                            "contact_channel", "priority", "res_t", "csat_score"])
    raw["customer_support"] = pd.DataFrame({
        "ticket_id": TK.ticket_id, "customer_id": TK.customer_id, "order_id": TK.order_id,
        "created_ts": ts_str(base, TK.t), "category": TK.category, "contact_channel": TK.contact_channel,
        "priority": TK.priority, "resolved_ts": ts_str(base, TK.res_t), "csat_score": TK.csat_score.astype("Int64")})

    # ---------------- experiments
    raw["experiments"] = pd.DataFrame([dict(
        experiment_id=e["experiment_id"], experiment_name=e["name"], hypothesis=e["hypothesis"],
        primary_metric=e["primary_metric"], randomisation_unit="customer", planned_split=e["planned_split"],
        start_date=str(e["start"]), end_date=str(e["end"]), owner="growth-product", status="completed")
        for e in S.EXPERIMENTS])
    A = pd.DataFrame(sim.assign)
    raw["experiment_assignments"] = pd.DataFrame({
        "assignment_id": [f"ASG-{i + 1:07d}" for i in range(len(A))], "experiment_id": A.experiment_id,
        "customer_id": A.customer_id, "variant": A.variant, "assigned_ts": ts_str(base, A.assigned_t),
        "platform": A.platform})
    raw["geography"] = geo.drop(columns=["weight"])
    raw["dates"] = dates_table(sim.days)

    # ---------------- defects
    raw = defects.apply_all(raw, rng)

    # ---------------- write batches
    out = Path(a.out)
    main_dir = out / str(cfg.extraction_date)
    late_dir = out / str(cfg.late_batch_date)
    main_dir.mkdir(parents=True, exist_ok=True)
    late_dir.mkdir(parents=True, exist_ok=True)
    rf = raw.pop("refunds")
    late_mask = rf._ext_t > X
    rf = rf.drop(columns=["_ext_t"])
    rf[~late_mask.values].to_csv(main_dir / "refunds.csv", index=False)
    rf[late_mask.values].to_csv(late_dir / "refunds.csv", index=False)
    for name, df in raw.items():
        df.to_csv(main_dir / f"{name}.csv", index=False)
    gt = out.parent / "ground_truth"
    gt.mkdir(parents=True, exist_ok=True)
    (gt / "defects.json").write_text(json.dumps(defects.LOG, indent=2))
    scen = {k: (str(v) if not isinstance(v, (int, float, list, tuple, dict)) else v)
            for k, v in vars(S).items() if k.isupper()}
    scen["EXPERIMENTS"] = [{k: str(v) for k, v in e.items()} for e in S.EXPERIMENTS]
    (gt / "scenarios.json").write_text(json.dumps(scen, indent=2, default=str))
    counts = {n: len(d) for n, d in raw.items()} | {"refunds": len(rf)}
    (gt / "row_counts.json").write_text(json.dumps(counts, indent=2))
    print(json.dumps(counts, indent=1))
    print(f"done in {time.time() - t0:.1f}s -> {out}")


if __name__ == "__main__":
    main()
