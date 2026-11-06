"""
Customer-lifecycle simulation.

Model (per customer):
  * signup time ~ demand calendar; acquisition channel & campaign
  * latent purchase rate lambda ~ Gamma (orders / 30 days while alive)
  * lifetime ~ Exponential(monthly churn hazard)  -> churn date
  * orders ~ inhomogeneous Poisson process (rate x festive demand), via thinning
  * membership (Nova Plus) join probability rises with latent loyalty  (S6 selection bias)
  * each order -> items, payment attempts (S2 failures), fulfilment, refunds (S3), tickets
  * each web/app order -> a converting session + funnel events
Times are float "days since cfg.start" in IST.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import scenarios as S
from .calendar import demand_index, festival_lookup
from .reference import (
    ACQ_CHANNELS,
    ACQ_PROBS,
    CATEGORIES,
    CHANNEL_CHURN,
    CHANNEL_LAMBDA,
    PAID_CHANNELS,
    PRICE_CHANGE_DATE,
)

HOUR_W = np.array([0.6, 0.35, 0.2, 0.15, 0.15, 0.25, 0.5, 0.9, 1.4, 1.9, 2.2, 2.4, 2.6, 2.5, 2.4,
                   2.3, 2.3, 2.5, 2.9, 3.5, 4.1, 4.4, 3.7, 2.0])
HOUR_P = HOUR_W / HOUR_W.sum()
PAY_METHODS = np.array(["UPI", "Card", "COD", "Wallet", "EMI"])
PAY_P_BY_TIER = {1: [0.55, 0.22, 0.10, 0.08, 0.05], 2: [0.57, 0.14, 0.20, 0.06, 0.03],
                 3: [0.52, 0.08, 0.33, 0.05, 0.02]}
BASE_FAIL = {"UPI": 0.06, "Card": 0.08, "Wallet": 0.04, "EMI": 0.10}
FAIL_REASONS = {"UPI": ["upi_timeout", "upi_collect_expired", "bank_declined"],
                "Card": ["insufficient_funds", "3ds_failed", "bank_declined"],
                "Wallet": ["insufficient_balance", "wallet_timeout"],
                "EMI": ["emi_not_eligible", "bank_declined"]}
REPEAT_TRAFFIC = ["direct", "organic_search", "email", "push", "paid_search", "paid_social"]
REPEAT_TRAFFIC_P = [0.30, 0.24, 0.16, 0.10, 0.12, 0.08]
ACQ_TO_TRAFFIC = {"organic": "organic_search", "paid_search": "paid_search", "paid_social": "paid_social",
                  "referral": "referral", "affiliate": "affiliate", "marketplace": "direct"}
REFUND_REASONS = ["changed_mind", "not_as_described", "defective", "size_issue", "late_delivery"]


class CommerceSim:
    def __init__(self, cfg, rng, geo: pd.DataFrame, prods: pd.DataFrame, camps: pd.DataFrame):
        self.cfg, self.rng = cfg, rng
        self.days = pd.date_range(cfg.start, cfg.end, freq="D")
        self.T = len(self.days)
        self.demand = demand_index(self.days)
        _, self.fest = festival_lookup(self.days)
        self.dmax = float(self.demand.max()) * 1.15
        self.geo = geo.reset_index(drop=True)
        self.geo_p = (geo.weight / geo.weight.sum()).values
        self.geo_state = geo.state.values
        self.geo_tier = geo.city_tier.values
        self.prods = prods.reset_index(drop=True)
        self.camps = camps
        self._prep_products()
        self._prep_campaigns()
        # outputs
        self.orders, self.items, self.payments, self.refunds = [], [], [], []
        self.tickets, self.subs, self.assign = [], [], []
        self.sessions, self.events = [], []
        self.order_seq = self.item_seq = self.pay_seq = self.ref_seq = self.tkt_seq = 0
        self.sess_seq = 0
        self.order_session = {}

    # ------------------------------------------------------------------ helpers
    def off(self, d):
        return (d - self.cfg.start).days

    def _prep_products(self):
        rng, P = self.rng, self.prods
        self.cat_names = list(CATEGORIES.keys())
        self.cat_p = np.array([CATEGORIES[c][5] for c in self.cat_names])
        self.cat_p = self.cat_p / self.cat_p.sum()
        self.p_cat = P.category.map({c: i for i, c in enumerate(self.cat_names)}).values
        self.p_brand = P.brand.values
        self.p_id = P.product_id.values
        self.p_price1 = P.list_price.values.astype(float)
        self.p_cost1 = P.unit_cost.values.astype(float)
        self.p_v2 = rng.random(len(P)) < 0.25
        self.p_price2 = np.round(self.p_price1 * rng.uniform(1.04, 1.10, len(P)))
        self.p_cost2 = np.round(self.p_cost1 * rng.uniform(1.05, 1.12, len(P)), 2)
        self.pc_off = self.off(PRICE_CHANGE_DATE)
        self.cat_idx, self.cat_pp = [], []
        for c in range(len(self.cat_names)):
            idx = np.where(self.p_cat == c)[0]
            w = P.popularity.values[idx]
            self.cat_idx.append(idx)
            self.cat_pp.append(w / w.sum())
        self.cat_refund = np.array([CATEGORIES[c][6] for c in self.cat_names])

    def _prep_campaigns(self):
        self.camp_by_ch = {}
        for r in self.camps.itertuples():
            if r.campaign_id == S.S1_CAMPAIGN_ID:
                continue
            self.camp_by_ch.setdefault(r.channel, []).append(
                (self.off(r.start_date), self.off(r.end_date) + 1, r.campaign_id, r.first_order_discount_pct,
                 "FEST" in r.campaign_id))

    def _campaign_for(self, ch, t):
        best = None
        for s, e, cid, disc, fest in self.camp_by_ch.get(ch, []):
            if s <= t < e:
                if fest and self.rng.random() < 0.5:
                    return cid, disc
                if not fest:
                    best = (cid, disc)
        return best if best else ("", 0.0)

    def _email_campaign(self, t):
        for s, e, cid, _disc, _fest in self.camp_by_ch["email"]:
            if s <= t < e:
                return cid
        return ""

    # ------------------------------------------------------------------ customers
    def make_customers(self):
        cfg, rng, T = self.cfg, self.rng, self.T
        n = cfg.n_customers
        n_blitz = int(n * S.S1_SHARE_OF_CUSTOMERS)
        n_legacy = int(n * S.LEGACY_SHARE)
        n_base = n - n_blitz - n_legacy
        w = self.demand * (1 + 0.5 * np.arange(T) / T)
        sd = rng.choice(T, n_base, p=w / w.sum()) + rng.random(n_base)
        sd = np.concatenate([sd, -S.LEGACY_DAYS + rng.random(n_legacy) * S.LEGACY_DAYS])  # 2023 signups
        n_base += n_legacy
        ch = rng.choice(ACQ_CHANNELS, n_base, p=ACQ_PROBS)
        bs, be = self.off(S.S1_START), self.off(S.S1_END) + 1
        wb = self.demand[bs:be]
        sd_b = bs + rng.choice(be - bs, n_blitz, p=wb / wb.sum()) + rng.random(n_blitz)
        signup = np.concatenate([sd, sd_b])
        chan = np.concatenate([ch, np.array(["paid_social"] * n_blitz)])
        blitz = np.concatenate([np.zeros(n_base, bool), np.ones(n_blitz, bool)])
        o = np.argsort(signup)
        signup, chan, blitz = signup[o], chan[o], blitz[o]

        C = pd.DataFrame({"signup_t": signup, "acq": chan, "blitz": blitz})
        C["customer_id"] = [f"CUS-{i + 1:06d}" for i in range(n)]
        C["geo1"] = rng.choice(len(self.geo), n, p=self.geo_p)
        C["moves"] = rng.random(n) < 0.12
        C["move_t"] = np.where(C.moves, signup + rng.uniform(30, 500, n), np.inf)
        C["geo2"] = np.where(C.moves, rng.choice(len(self.geo), n, p=self.geo_p), C.geo1)
        camp, disc = [], []
        for t, a, b in zip(signup, chan, blitz):
            if b:
                camp.append(S.S1_CAMPAIGN_ID); disc.append(S.S1_DISCOUNT)
            elif a in PAID_CHANNELS and t >= 0:
                c, d = self._campaign_for(a, t); camp.append(c); disc.append(d)
            else:
                camp.append(""); disc.append(0.0)
        C["campaign_id"], C["camp_disc"] = camp, disc
        lam_mean = np.where(blitz, S.S1_LAMBDA_MEAN, C.acq.map(CHANNEL_LAMBDA).values)
        C["lam"] = rng.gamma(1.6, lam_mean / 1.6)
        hazard = np.where(blitz, S.S1_MONTHLY_CHURN, C.acq.map(CHANNEL_CHURN).values)
        C["is_buyer"] = rng.random(n) < np.where(blitz, 0.85, 0.62)
        C["first_t"] = signup + rng.exponential(np.where(blitz, 1.0, 5.0))
        C["churn_t"] = C.first_t + rng.exponential(30.0 / hazard)
        C["lam_pct"] = C.lam.rank(pct=True)
        C["device"] = rng.choice(["mobile_app", "mobile_web", "desktop"], n, p=[0.45, 0.33, 0.22])
        C["ios"] = rng.random(n) < 0.20
        C["mkt_share"] = np.where(C.acq == "marketplace", 0.75, 0.06)
        C["is_test"] = False
        test_idx = rng.choice(np.where(C.is_buyer & ~C.blitz & (C.signup_t < 200))[0], 40, replace=False)
        C.loc[test_idx, ["is_test", "lam"]] = [True, 0.9]
        C["opt_in"] = (rng.random(n) < 0.7).astype(int)
        self.C = C
        return C

    # ------------------------------------------------------------------ experiments
    def _exp_ctx(self, i, r):
        ctx = []
        if not r.is_buyer or r.is_test:
            return ctx
        for e in S.EXPERIMENTS:
            s, en = self.off(e["start"]), self.off(e["end"]) + 1
            if r.first_t <= s < r.churn_t:
                variant = "treatment" if self.rng.random() < e["planned_split"] else "control"
                a_t = s + self.rng.uniform(0, 7)
                ctx.append(dict(exp=e, variant=variant, a_t=a_t, end=en, n_in=0))
        return ctx

    # ------------------------------------------------------------------ main loop
    def run(self):
        C, rng, T = self.C, self.rng, self.T
        launch = self.off(S.MEMBERSHIP_LAUNCH)
        for i, r in enumerate(C.itertuples()):
            if not r.is_buyer or r.first_t >= T:
                continue
            ctx = dict(i=i, cid=r.customer_id, geo1=r.geo1, geo2=r.geo2, move_t=r.move_t,
                       device=r.device, ios=r.ios, mkt_share=r.mkt_share, blitz=r.blitz,
                       camp=r.campaign_id, camp_disc=r.camp_disc, acq=r.acq,
                       pay_p=PAY_P_BY_TIER[int(self.geo_tier[r.geo1])], member=False)
            exps = self._exp_ctx(i, r)
            churn_t = r.churn_t
            end_t = min(churn_t, T)
            lam = r.lam
            m_start = m_end = math.inf
            plan = None
            t, k = r.first_t, 0
            while True:
                ctx["member"] = m_start <= t < m_end
                thr = 499
                for x in exps:
                    if x["a_t"] <= t < x["end"]:
                        x["n_in"] += 1
                        if x["exp"]["experiment_id"] == "EXP-2025-02" and x["variant"] == "treatment":
                            thr = 299
                if t >= 0:                      # pre-2024 (legacy) orders are simulated but not migrated
                    self._order(ctx, t, k, thr)
                k += 1
                if (plan is None and k >= 2 and t >= launch and not r.is_test
                        and rng.random() < 0.03 + 0.42 * r.lam_pct ** 2):
                    m_start = t + rng.uniform(0.01, 3)
                    plan = "annual" if rng.random() < 0.3 else "monthly"
                    m_end = m_start + (365 * (1 + (rng.random() < 0.55)) if plan == "annual"
                                       else rng.exponential(300))
                    churn_t = t + (churn_t - t) * S.MEMBER_TRUE_LIFETIME_EXT
                    end_t = min(churn_t, T)
                # next order (thinning)
                while True:
                    is_mem = m_start <= t < m_end
                    rate = lam * (S.MEMBER_TRUE_RATE_LIFT if is_mem else 1.0)
                    t += rng.exponential(30.0 / (rate * self.dmax))
                    if t >= end_t:
                        break
                    acc = (self.demand[int(t)] if t >= 0 else self.demand[:60].mean() * 0.9) / self.dmax
                    for x in exps:
                        if x["variant"] == "treatment" and x["a_t"] <= t < x["end"]:
                            acc *= 1 + x["exp"]["true_lift"]
                    if rng.random() < acc:
                        break
                if t >= end_t:
                    break
            if plan:
                if plan == "monthly":
                    m_end = min(m_end, churn_t + rng.uniform(15, 60))
                self.subs.append(dict(customer_id=r.customer_id, plan_type=plan,
                                      start_t=m_start, end_t=m_end if m_end < T else np.nan,
                                      fee=149.0 if plan == "monthly" else 999.0))
            for x in exps:
                e = x["exp"]
                if (e["srm_bug"] and x["variant"] == "treatment" and x["n_in"] == 0
                        and rng.random() < S.S5_SRM_DROP_PROB):
                    continue  # logging bug: assignment never written
                self.assign.append(dict(experiment_id=e["experiment_id"], customer_id=r.customer_id,
                                        variant=x["variant"], assigned_t=x["a_t"],
                                        platform=("ios" if r.ios else "android") if r.device == "mobile_app"
                                        else r.device))
        self._guest_orders()

    def _guest_orders(self):
        rng = self.rng
        n_guest = int(len(self.orders) * 0.025)
        tt = rng.choice(self.T, n_guest, p=self.demand / self.demand.sum()) + rng.random(n_guest)
        for t in tt:
            g = rng.choice(len(self.geo), p=self.geo_p)
            ctx = dict(i=-1, cid=None, geo1=g, geo2=g, move_t=np.inf,
                       device=rng.choice(["mobile_web", "desktop"]), ios=rng.random() < 0.2, mkt_share=0.0,
                       blitz=False, camp="", camp_disc=0.0, acq="organic",
                       pay_p=[0.45, 0.10, 0.45, 0.0, 0.0], member=False)
            self._order(ctx, t, 1, 499)

    # ------------------------------------------------------------------ one order
    def _order(self, ctx, t, k, ship_thr):
        rng = self.rng
        d = min(int(t), self.T - 1)
        t = d + (rng.choice(24, p=HOUR_P) + rng.random()) / 24.0
        geo = ctx["geo2"] if t >= ctx["move_t"] else ctx["geo1"]
        state, tier = self.geo_state[geo], int(self.geo_tier[geo])
        if rng.random() < ctx["mkt_share"]:
            channel, device, os_ = "marketplace", "unknown", ""
        else:
            device = ctx["device"] if rng.random() < 0.8 else rng.choice(["mobile_app", "mobile_web", "desktop"])
            channel = "app" if device == "mobile_app" else "web"
            if device == "desktop":
                os_ = "macos" if rng.random() < 0.15 else "windows"
            else:
                os_ = "ios" if ctx["ios"] else "android"
        self.order_seq += 1
        oid = f"ORD-{self.order_seq:07d}"
        member = ctx["member"]
        # ---- items
        lines, subtotal = [], 0.0
        n_items = 1 + min(rng.poisson(0.55), 5)
        for c in rng.choice(len(self.cat_names), n_items, p=self.cat_p):
            p = self.cat_idx[c][rng.choice(len(self.cat_idx[c]), p=self.cat_pp[c])]
            v2 = self.p_v2[p] and t >= self.pc_off
            price = self.p_price2[p] if v2 else self.p_price1[p]
            cost = self.p_cost2[p] if v2 else self.p_cost1[p]
            cname = self.cat_names[c]
            if self.fest[d] > 1.2 and cname in ("Fashion", "Electronics", "Home & Kitchen"):
                disc = rng.uniform(0.15, 0.30)
            elif rng.random() < 0.3:
                disc = rng.uniform(0.05, 0.12)
            else:
                disc = 0.0
            if member:
                disc += 0.05
            sale = float(np.round(price * (1 - disc)))
            qty = 1 if rng.random() < 0.85 else int(rng.integers(2, 4))
            if cname in ("Grocery & Gourmet", "Home & Kitchen") and rng.random() < 0.0012:
                qty = int(rng.integers(40, 150))       # B2B bulk order (legit outlier)
            lines.append([p, qty, price, sale, cost, c])
            subtotal += qty * sale
        # ---- coupon
        coupon, cdisc = "", 0.0
        if k == 0 and ctx["camp_disc"] > 0:
            rate = ctx["camp_disc"]
            cap = 750 if ctx["blitz"] else 400
            coupon = {0.1: "WELCOME10", 0.2: "FEST20", 0.4: "BLITZ40"}.get(round(rate, 2), "WELCOME")
            cdisc = round(min(subtotal * rate, cap), 2)
        elif rng.random() < 0.08:
            coupon, cdisc = "NOVA10", round(min(subtotal * 0.10, 200), 2)
        fee = 49.0 if (not member and channel != "marketplace" and subtotal - cdisc < ship_thr) else 0.0
        total = round(subtotal - cdisc + fee, 2)
        if channel == "marketplace":
            ship_cost, commission = 0.0, round(0.15 * subtotal, 2)
        else:
            ship_cost = round(max(35.0, 55 + 0.012 * subtotal + {1: 0, 2: 10, 3: 25}[tier] + rng.normal(0, 5)), 2)
            commission = 0.0
        # ---- payment
        method = PAY_METHODS[rng.choice(5, p=ctx["pay_p"])]
        if method == "EMI" and subtotal < 3000:
            method = "Card"
        gateway = "mkt_settlement" if channel == "marketplace" else (
            "cod" if method == "COD" else ("razorpay" if rng.random() < 0.7 else "payu"))
        s2 = (device == "mobile_app" and method == "UPI" and self.off(S.S2_START) <= t < self.off(S.S2_END))
        s2_fail = S.S2_UPI_FAIL_PROB if state in S.S2_STATES else S.S2_UPI_FAIL_PROB_OTHER
        pay_rows, paid, pt = [], method == "COD", t + rng.uniform(2, 6) / 1440
        if method != "COD":
            m = method
            for att in (1, 2, 3):
                pf = s2_fail if (s2 and m == "UPI") else BASE_FAIL[m]
                ok = rng.random() >= pf
                reason = "" if ok else ("upi_intent_launch_failed" if (s2 and m == "UPI" and rng.random() < 0.8)
                                        else rng.choice(FAIL_REASONS[m]))
                pay_rows.append([att, pt, m, gateway, total, "success" if ok else "failed", reason])
                if ok:
                    paid = True
                    break
                if rng.random() > (0.55 if att == 1 else 0.3):
                    break
                pt += rng.uniform(1, 5) / 1440
                if s2 and m == "UPI" and rng.random() < 0.35:
                    m = "Card"
        status, ship_t, deliv_t, canc_t = None, np.nan, np.nan, np.nan
        if not paid:
            status = "payment_failed"
        elif rng.random() < (0.09 if method == "COD" else 0.03):
            status, canc_t = "cancelled", t + rng.uniform(0.05, 1.5)
        else:
            ship_t = t + rng.uniform(0.4, 2.5)
            lo, hi = {1: (1, 3), 2: (2, 5), 3: (3, 8)}[tier]
            deliv_t = ship_t + rng.uniform(lo, hi)
            if deliv_t <= self.T:
                status = "delivered"
            elif ship_t <= self.T:
                status, deliv_t = "shipped", np.nan
            else:
                status, ship_t, deliv_t = "processing", np.nan, np.nan
        if method == "COD" and status == "delivered":
            pay_rows.append([1, deliv_t, "COD", "cod", total, "success", ""])
        for att, ts, m, gw, amt, st, reason in pay_rows:
            self.pay_seq += 1
            fee_g = round(35.0 if gw == "cod" else amt * (0.02 if gw == "razorpay" else 0.019), 2) \
                if st == "success" else 0.0
            self.payments.append((f"PAY-{self.pay_seq:08d}", oid, att, ts, m, gw, amt, st, reason,
                                  f"TXN{rng.integers(10**11, 10**12)}", fee_g))
        # ---- persist order + items
        self.orders.append((oid, ctx["cid"], t, channel, device, os_, self.geo.geo_id.iat[geo], method,
                            coupon, round(subtotal, 2), cdisc, fee, total, ship_cost, commission, status,
                            ship_t, deliv_t, canc_t, k == 0, ctx["i"], s2))
        item_ids = []
        for p, qty, price, sale, _cost, _c in lines:
            self.item_seq += 1
            iid = f"OI-{self.item_seq:08d}"
            item_ids.append(iid)
            self.items.append((iid, oid, self.p_id[p], qty, price, sale))
        # ---- cancellation refund (order-level; NOT a return)
        if status == "cancelled" and method != "COD":
            self._refund(oid, None, canc_t + rng.uniform(0.1, 3), total, "order_cancelled")
        # ---- returns / refunds (item-level)
        late_delivery = False
        if status == "delivered":
            late_delivery = (deliv_t - t) > 7
            for iid, (p, qty, _price, sale, _cost, c) in zip(item_ids, lines):
                pr = self.cat_refund[c]
                s3 = self.p_brand[p] == S.S3_BRAND and t >= self.off(S.S3_START)
                if s3:
                    s3o = self.off(S.S3_START)
                    pr = 0.06 + (S.S3_REFUND_PROB_END - 0.06) * (t - s3o) / (self.T - s3o)
                pr *= (1.3 if method == "COD" else 1.0) * (S.S1_REFUND_MULT if ctx["blitz"] else 1.0) \
                    * (1.3 if late_delivery else 1.0)
                if rng.random() < pr:
                    line_net = qty * sale - (cdisc * qty * sale / subtotal if subtotal else 0)
                    amt = round(line_net * (0.5 if rng.random() < 0.1 else 1.0), 2)
                    if s3 and rng.random() < 0.7:
                        reason = "defective"
                    elif self.cat_names[c] == "Fashion" and rng.random() < 0.6:
                        reason = "size_issue"
                    elif late_delivery and rng.random() < 0.4:
                        reason = "late_delivery"
                    else:
                        reason = rng.choice(REFUND_REASONS, p=[0.35, 0.3, 0.15, 0.1, 0.1])
                    rt = deliv_t + rng.uniform(1, 14)
                    self._refund(oid, iid, rt, amt, reason, brand=self.p_brand[p])
        # ---- support tickets
        if ctx["cid"] is not None:
            if status == "payment_failed" and rng.random() < 0.25:
                self._ticket(ctx["cid"], oid, t + rng.uniform(0.01, 1), "payment_issue")
            if late_delivery and rng.random() < 0.3:
                self._ticket(ctx["cid"], oid, t + rng.uniform(5, 8), "delivery_delay")
            if rng.random() < 0.02:
                self._ticket(ctx["cid"], oid, t + rng.uniform(0, 10), rng.choice(["account", "other", "order_change"]))
        # ---- converting session + funnel events
        if channel != "marketplace":
            self.order_session[oid] = self._order_session(ctx, t, k, device, os_, geo, lines, pay_rows, paid)

    def _refund(self, oid, iid, rt, amt, reason, brand=None):
        rng = self.rng
        if rt > self.T + 11:          # beyond last extract
            return
        self.ref_seq += 1
        st = "processed" if rng.random() < 0.93 else ("rejected" if rng.random() < 0.45 else "pending")
        self.refunds.append((f"RF-{self.ref_seq:07d}", oid, iid, rt, amt, reason, st, rt + rng.uniform(0, 10)))
        cid = self.orders[-1][1]
        if iid is not None and cid is not None and rng.random() < 0.4:
            cat = "product_defect" if reason == "defective" else "return_refund"
            self._ticket(cid, oid, rt - rng.uniform(0, 1), cat)

    def _ticket(self, cid, oid, ts, cat):
        rng = self.rng
        if ts > self.T:
            return
        self.tkt_seq += 1
        res_h = float(np.round(rng.lognormal(2.6 if cat != "product_defect" else 3.2, 0.8), 1))
        csat_mu = {"payment_issue": 2.8, "product_defect": 2.5, "delivery_delay": 3.0}.get(cat, 3.8)
        csat = int(np.clip(np.round(rng.normal(csat_mu, 1.0)), 1, 5)) if rng.random() < 0.6 else None
        self.tickets.append((f"TKT-{self.tkt_seq:07d}", cid, oid, ts, cat,
                             rng.choice(["chat", "email", "phone"], p=[0.55, 0.3, 0.15]),
                             "high" if cat in ("payment_issue", "product_defect") else "normal",
                             ts + res_h / 24 if rng.random() < 0.95 else np.nan, csat))

    def _order_session(self, ctx, t, k, device, os_, geo, lines, pay_rows, paid):
        rng = self.rng
        self.sess_seq += 1
        sid = self.sess_seq
        st = t - rng.uniform(5, 30) / 1440
        if k == 0 and ctx["cid"] is not None:
            traffic = ACQ_TO_TRAFFIC[ctx["acq"]]
            utm = ctx["camp"] if ctx["acq"] in PAID_CHANNELS else ""
        else:
            traffic = rng.choice(REPEAT_TRAFFIC, p=REPEAT_TRAFFIC_P)
            if traffic == "push" and device != "mobile_app":
                traffic = "direct"
            utm = self._email_campaign(t) if traffic == "email" else ""
        self.sessions.append((sid, ctx["cid"], st, device, os_, geo, traffic, utm, True))
        ev = self.events
        n = len(lines)
        step = (t - st) / (2 * n + 2)
        for j, (p, *_) in enumerate(lines):
            ev.append((sid, st + (j + 1) * step, "product_view", self.p_id[p]))
        for j, (p, *_) in enumerate(lines):
            ev.append((sid, st + (n + j + 1) * step, "add_to_cart", self.p_id[p]))
        ev.append((sid, t - 30 / 86400, "begin_checkout", None))
        prepaid = [r for r in pay_rows if r[2] != "COD" or r[3] != "cod"]
        if not prepaid:                      # COD: placing the order is the "payment" step
            ev.append((sid, t + 60 / 86400, "payment_attempt", None))
            ev.append((sid, t + 61 / 86400, "purchase", None))
            return sid
        for r in prepaid:
            ev.append((sid, r[1], "payment_attempt", None))
            if r[5] == "success":
                ev.append((sid, r[1] + 1 / 86400, "purchase", None))
        return sid
