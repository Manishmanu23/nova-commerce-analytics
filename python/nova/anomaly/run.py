"""
Anomaly detection pipeline (two levels).

LEVEL 1  top-line governed metrics, daily (weekly for slow metrics)       -> incidents
LEVEL 2  segment scan for ratio metrics, weekly, per dimension value      -> segment incidents
         (averages hide problems: a 40% failure spike in 3 states is -2% at national level)
Then:    contribution drill-down, and classification: business_signal | expected_seasonal | data_quality
Outputs: analytics.anomaly_scores, analytics.anomaly_alerts, analytics.anomaly_segment_alerts,
         analytics.anomaly_drilldown, reports/anomaly_detection.md

An alert says "this is unusual, this big, concentrated here". It does NOT say why.
"""
import json

import numpy as np
import pandas as pd

from nova.anomaly.detectors import rate_binomial_z, seasonal_robust_z, stl_residual_z
from nova.common.db import read_sql, write_df
from nova.common.report import ROOT, md_table, write

# metric: kind, numerator, denominator, bad direction, display name, grain
METRICS = {
    "net_revenue":          ("value", "net_revenue", None, "both", "Net Revenue", "D"),
    "orders":               ("value", "orders", None, "both", "Completed Orders", "D"),
    "sessions_incl_bots":   ("value", "sessions_incl_bots", None, "both", "Sessions (incl. bots)", "D"),
    "aov":                  ("ratio", "aov_order_value", "aov_orders", "both", "Average Order Value", "D"),
    "conversion_rate":      ("binomial", "purchase_sessions", "sessions", "down", "Session Conversion", "D"),
    "checkout_conversion":  ("binomial", "purchase_sessions", "checkout_sessions", "down", "Checkout Conversion", "D"),
    "payment_success_rate": ("binomial", "successful_payment_attempts", "payment_attempts", "down", "Payment Success", "D"),
    "refund_rate":          ("ratio", "return_refund_amount", "gross_revenue", "up", "Refund Rate (value)", "W"),
}
SEGMENT_SCAN = {
    "payment_success_rate": ("successful_payment_attempts", "payment_attempts",
                             ["payment_method", "device_type", "state", "app_version"]),
    "checkout_conversion": ("purchase_sessions", "checkout_sessions",
                            ["device_type", "state", "app_version", "browser", "traffic_channel"]),
}
DRILL_DIMS = {
    "net_revenue": ["channel", "device_type", "state", "customer_type", "category"],
    "orders": ["channel", "device_type", "state", "customer_type"],
    "checkout_conversion": ["device_type", "state", "app_version", "browser"],
    "conversion_rate": ["device_type", "state", "traffic_channel", "browser"],
    "payment_success_rate": ["payment_method", "device_type", "state", "app_version"],
}
Z_THR, MIN_DEV, SEG_Z, SEG_DEV, SEG_MIN_DEN = 4.0, 0.10, 4.0, 0.10, 100


def fmt_value(metric, v):
    if METRICS[metric][0] == "binomial" or metric == "refund_rate":
        return f"{v:.2%}"
    return f"₹{v:,.0f}" if metric in ("net_revenue", "aov") else f"{v:,.0f}"


def severity(dev, impact):
    a = abs(dev)
    if a >= 0.20 or abs(impact) >= 200_000:
        return "High"
    if a >= 0.12 or abs(impact) >= 50_000:
        return "Medium"
    return "Low"


# ---------------------------------------------------------------- data
def load_daily():
    d = read_sql("select m.*, dd.is_sale_period, coalesce(dd.festival_name, '') as festival_name "
                 "from metrics.metrics_daily m join marts.dim_date dd using (date_day) order by date_day")
    d["date_day"] = pd.to_datetime(d.date_day)
    d = d.set_index("date_day").asfreq("D")
    d["sessions_incl_bots"] = d.sessions + d.bot_sessions
    num_cols = [c for c in d.columns if c not in ("is_sale_period", "festival_name", "is_refund_mature")]
    d[num_cols] = d[num_cols].astype(float)
    # sale days + the 3 days after a sale are "special" -> masked out of baselines
    sale = d.is_sale_period.astype(bool)
    d["special"] = sale | sale.shift(1, fill_value=False) | sale.shift(2, fill_value=False) | sale.shift(3, fill_value=False)
    return d


def to_weekly(d, cols):
    w = d[cols].resample("W-SUN").sum()
    w["special"] = d.special.resample("W-SUN").max().astype(bool)
    w["is_sale_period"] = d.is_sale_period.astype(bool).resample("W-SUN").max()
    w["festival_name"] = d.festival_name.resample("W-SUN").agg(lambda x: ", ".join(sorted(set(x) - {""})))
    w["mature"] = d.is_refund_mature.astype(bool).resample("W-SUN").min()
    return w.iloc[:-1] if d.index[-1].dayofweek != 6 else w


# ---------------------------------------------------------------- level 1
def score_topline(d):
    out = []
    for m, (kind, num, den, bad, disp, grain) in METRICS.items():
        x = d if grain == "D" else to_weekly(d, [num] + ([den] if den else []))
        season = 7 if grain == "D" else 1
        mask = x.special
        if kind == "value":
            a = seasonal_robust_z(x[num], season=season, mask=mask)
            a["z_check"] = stl_residual_z(x[num]).z if grain == "D" else np.nan
        elif kind == "ratio":
            a = seasonal_robust_z(x[num] / x[den].replace(0, np.nan), season=season, mask=mask,
                                  noise_window=91 if grain == "D" else 26)
            a["z_check"] = np.nan
        else:
            a = rate_binomial_z(x[num], x[den], season=season, mask=mask)
            a["z_check"] = np.nan
        a["num"] = x[num]
        a["den"] = x[den] if den else np.nan
        if m == "refund_rate":
            a.loc[~x.mature.astype(bool), "z"] = np.nan          # immature refund weeks are not judged
        a["metric"], a["display"], a["grain"] = m, disp, grain
        a["special"], a["is_sale_period"], a["festival_name"] = x.special, x.is_sale_period, x.festival_name
        dirok = {"down": a.z < 0, "up": a.z > 0, "both": a.z.notna()}[bad]
        a["is_anomaly"] = (a.z.abs() >= Z_THR) & (a.deviation.abs() >= MIN_DEV) & dirok
        out.append(a.rename_axis("period").reset_index())
    return pd.concat(out, ignore_index=True)


def merge_incidents(flags: pd.DataFrame, key_cols, gap_days):
    rows = []
    for key, g in flags.groupby(key_cols):
        g = g.sort_values("period")
        grp = (g.period.diff().dt.days.fillna(999) > gap_days).cumsum()
        for _, x in g.groupby(grp):
            rows.append((key, x))
    return rows


def build_incidents(scores, d):
    rows = []
    for (m,), x in merge_incidents(scores[scores.is_anomaly], ["metric"], 3):
        kind, num, den, bad, disp, grain = METRICS[m]
        s, e = x.period.min(), x.period.max()
        if kind == "value":
            actual, expected = x.actual.sum(), x.expected.sum()
            impact = actual - expected
        else:
            w = x.den.fillna(1)
            actual = x.num.sum() / x.den.sum()
            expected = float((x.expected * w).sum() / w.sum())
            if m == "refund_rate":
                impact = -(actual - expected) * x.den.sum()
            elif m == "aov":
                impact = (actual - expected) * x.den.sum()
            else:   # lost conversions/payments x median order value
                impact = (actual - expected) * x.den.sum() * float(d.aov.median())
        dev = actual / expected - 1
        start = s - pd.Timedelta(days=6) if grain == "W" else s
        rows.append(dict(metric=m, display=disp, grain=grain, start_date=start.date(), end_date=e.date(),
                         periods=len(x), expected=expected, actual=actual, deviation=dev,
                         max_abs_z=float(x.z.abs().max()),
                         stl_confirms=bool((x.z_check.abs() >= 3).any()) if grain == "D" and kind == "value" else None,
                         during_special=bool(x.special.any()),
                         festival=", ".join(sorted({f for f in x.festival_name if f})) or None,
                         est_impact_inr=float(impact), severity=severity(dev, impact)))
    return pd.DataFrame(rows)


def classify(inc):
    raw_dup = read_sql("""
        select ((order_ts::timestamp at time zone 'UTC') at time zone 'Asia/Kolkata')::date as d,
               count(*)::float / count(distinct order_id) - 1 as dup_rate
        from raw.orders where order_ts ~ '^202[45]-' group by 1""").set_index("d").dup_rate
    bots = read_sql("select session_date as d, avg(is_bot::int) as bot_share from staging.stg_web_sessions "
                    "group by 1").set_index("d").bot_share
    bulk = read_sql("select order_date as d, sum(net_revenue) as bulk_rev, count(*) as n from marts.fct_orders "
                    "where is_countable and is_bulk_order group by 1").set_index("d")
    labels, notes = [], []
    for r in inc.itertuples():
        days = pd.date_range(r.start_date, r.end_date).date
        bot = max((bots.get(x, 0) for x in days), default=0)
        b_rev = sum(float(bulk.bulk_rev.get(x, 0)) for x in days)
        excess = r.actual - r.expected if r.metric in ("net_revenue", "orders") else 0
        dup = max((raw_dup.get(x, 0) for x in days), default=0)
        if bot > 0.05:
            labels.append("data_quality"); notes.append(f"bot sessions = {bot:.0%} of traffic (flagged is_bot, excluded from governed conversion)")
        elif r.metric == "net_revenue" and excess > 0 and b_rev >= 0.5 * excess:
            labels.append("one_off_outlier")
            notes.append(f"B2B bulk order(s) worth ₹{b_rev:,.0f} explain most of the excess; legitimate revenue, "
                         "excluded from AOV, not a trend")
        elif r.during_special:
            labels.append("expected_seasonal"); notes.append(f"sale/festival window: {r.festival or 'post-sale days'}")
        else:
            labels.append("business_signal"); notes.append("no data-quality marker on these dates")
        if dup > 0.2:
            notes[-1] += f"; raw duplicate rate {dup:.0%} on this date (removed in staging)"
    inc = inc.copy()
    inc["classification"], inc["evidence_note"] = labels, notes
    return inc


# ---------------------------------------------------------------- level 2
def segment_scan(d):
    rows, scored = [], []
    special_w = d.special.resample("W-SUN").max().astype(bool)
    for m, (num, den, dims) in SEGMENT_SCAN.items():
        for dim in dims:
            q = read_sql(f"select date_day, dimension_value, {num} as num, {den} as den "
                         "from metrics.metrics_daily_by_dimension where dimension_name = :dim", dict(dim=dim))
            q["date_day"] = pd.to_datetime(q.date_day)
            for val, g in q.groupby("dimension_value"):
                w = g.set_index("date_day")[["num", "den"]].asfreq("D").fillna(0).resample("W-SUN").sum().iloc[:-1]
                if w.den.median() < SEG_MIN_DEN / 2:
                    continue
                z = rate_binomial_z(w.num, w.den, season=1, n_lags=8, mask=special_w.reindex(w.index).fillna(False),
                                    phi_window=26)
                z["flag"] = (z.z <= -SEG_Z) & (z.deviation <= -SEG_DEV) & (z.denominator >= SEG_MIN_DEN)
                z = z.assign(metric=m, dimension=dim, dimension_value=val).rename_axis("period").reset_index()
                scored.append(z)
    if not scored:
        return pd.DataFrame(), pd.DataFrame()
    allz = pd.concat(scored, ignore_index=True)
    for (m, dim, val), x in merge_incidents(allz[allz.flag], ["metric", "dimension", "dimension_value"], 8):
        rows.append(dict(metric=m, display=METRICS[m][4], dimension=dim, dimension_value=val,
                         start_date=(x.period.min() - pd.Timedelta(days=6)).date(), end_date=x.period.max().date(),
                         weeks=len(x), expected=float((x.expected * x.denominator).sum() / x.denominator.sum()),
                         actual=float(x.actual.mul(x.denominator).sum() / x.denominator.sum()),
                         volume=float(x.denominator.sum()), max_abs_z=float(x.z.abs().max())))
    seg = pd.DataFrame(rows)
    if not seg.empty:
        seg["deviation"] = seg.actual / seg.expected - 1
        seg["severity"] = np.where((seg.deviation <= -0.20) | ((seg.deviation <= -0.10) & (seg.max_abs_z >= 6)), "High",
                                   np.where(seg.deviation <= -0.10, "Medium", "Low"))
        seg = seg.sort_values(["start_date", "metric", "deviation"]).reset_index(drop=True)
    return seg, allz


# ---------------------------------------------------------------- drill-down
def drilldown(incs):
    out = []
    for r in incs.itertuples():
        if r.metric not in DRILL_DIMS:
            continue
        kind, num, den, *_ = METRICS[r.metric]
        s, e = pd.Timestamp(r.start_date), pd.Timestamp(r.end_date)
        base_s = s - pd.Timedelta(days=56)
        for dim in DRILL_DIMS[r.metric]:
            q = read_sql(f"select date_day, dimension_value, {num} as num, {den or 'null'} as den "
                         "from metrics.metrics_daily_by_dimension where dimension_name = :dim "
                         "and date_day between :a and :b", dict(dim=dim, a=base_s.date(), b=e.date()))
            if q.empty:
                continue
            q["date_day"] = pd.to_datetime(q.date_day)
            cur = q[q.date_day >= s].groupby("dimension_value")[["num", "den"]].sum()
            base = q[q.date_day < s].groupby("dimension_value")[["num", "den"]].sum()
            j = cur.astype(float).join(base.astype(float), rsuffix="_base", how="left").fillna(0)
            ndays = (e - s).days + 1
            if den:
                j["rate_base"] = j.num_base / j.den_base.replace(0, np.nan)
                j["rate_cur"] = j.num / j.den.replace(0, np.nan)
                j["contribution"] = j.num - j.rate_base * j.den       # volume held at current level
                j = j[j.den >= 20]
            else:
                j["rate_base"] = j["rate_cur"] = np.nan
                j["contribution"] = j.num - j.num_base / 56 * ndays
            tot = j.contribution.sum()
            j["share"] = j.contribution / tot if tot else np.nan
            j = j.reindex(j.contribution.abs().sort_values(ascending=False).index).head(5)
            for v, x in j.iterrows():
                out.append(dict(metric=r.metric, start_date=r.start_date, dimension=dim, dimension_value=v,
                                baseline_rate=x.rate_base, current_rate=x.rate_cur, contribution=x.contribution,
                                share_of_deviation=x.share))
    return pd.DataFrame(out)


SEG_FACT = {  # metric -> (sql over the fact, success flag, attempt filter) ; dimension columns available
    "payment_success_rate": ("""select p.payment_date as d, p.payment_method, p.device_type, coalesce(p.app_version,'n/a') as app_version,
                                     g.state, p.is_success::int as num, 1 as den
                              from marts.fct_payments p join marts.dim_geography g using (geo_id)
                              where p.is_prepaid_attempt and p.is_reportable and p.payment_date between :a and :b""",
                             ["state", "payment_method", "app_version", "device_type"]),
    "checkout_conversion": ("""select s.session_date as d, s.device_type, coalesce(s.app_version,'n/a') as app_version, s.browser,
                                    s.traffic_channel, g.state, s.has_purchase::int as num, 1 as den
                             from marts.fct_sessions s join marts.dim_geography g using (geo_id)
                             where not s.is_bot and s.has_begin_checkout and s.session_date between :a and :b""",
                            ["state", "app_version", "browser", "traffic_channel", "device_type"]),
}


def segment_drill(seg):
    """Inside a flagged segment (e.g. device_type = mobile_app), which OTHER dimension values carry the drop?"""
    out = []
    for r in seg.itertuples():
        sql, dims = SEG_FACT[r.metric]
        s0, e0 = pd.Timestamp(r.start_date), pd.Timestamp(r.end_date)
        q = read_sql(sql, dict(a=(s0 - pd.Timedelta(days=56)).date(), b=e0.date()))
        q = q[q[r.dimension].astype(str) == str(r.dimension_value)]
        q["d"] = pd.to_datetime(q.d)
        cur, base = q[q.d >= s0], q[q.d < s0]
        for dim in [x for x in dims if x != r.dimension]:
            c = cur.groupby(dim)[["num", "den"]].sum()
            b = base.groupby(dim)[["num", "den"]].sum()
            j = c.join(b, rsuffix="_b", how="left").fillna(0)
            j["rate_b"], j["rate_c"] = j.num_b / j.den_b.replace(0, np.nan), j.num / j.den.replace(0, np.nan)
            overall_b = base.num.sum() / max(base.den.sum(), 1)
            j["contribution"] = j.num - j.rate_b.fillna(overall_b) * j.den
            tot = j.contribution.sum()
            j["share"] = j.contribution / tot if tot else np.nan
            j = j[j.den >= 20].reindex(j.contribution.abs().sort_values(ascending=False).index).dropna(subset=["share"]).head(3)
            for v, x in j.iterrows():
                out.append(dict(metric=r.metric, segment=f"{r.dimension}={r.dimension_value}", start_date=r.start_date,
                                dimension=dim, dimension_value=v, baseline_rate=x.rate_b, current_rate=x.rate_c,
                                share_of_deviation=x.share))
    return pd.DataFrame(out)


# ---------------------------------------------------------------- raw layer
def raw_layer_scan():
    r = read_sql("""
        select ((order_ts::timestamp at time zone 'UTC') at time zone 'Asia/Kolkata')::date as date_day,
               count(*) as raw_rows, count(distinct order_id) as distinct_orders
        from raw.orders where order_ts ~ '^202[45]-' group by 1 order by 1""")
    r["date_day"] = pd.to_datetime(r.date_day)
    r = r.set_index("date_day").asfreq("D").fillna(0)
    z = seasonal_robust_z(r.raw_rows.astype(float))
    z["dup_rate"] = r.raw_rows / r.distinct_orders.replace(0, np.nan) - 1
    return z[(z.z > Z_THR) & (z.dup_rate > 0.2)].rename_axis("date_day").reset_index()


# ---------------------------------------------------------------- report
def card_topline(r, dd):
    lines = [f"**Metric:** {r.display}  ", f"**Window:** {r.start_date} → {r.end_date}  ",
             f"**Expected:** {fmt_value(r.metric, r.expected)}  ", f"**Actual:** {fmt_value(r.metric, r.actual)}  ",
             f"**Deviation:** {r.deviation:+.1%} (max robust |z| {r.max_abs_z:.1f}"
             + (f"; STL confirms: {r.stl_confirms}" if r.stl_confirms is not None else "") + ")  ",
             f"**Severity:** {r.severity}  ", f"**Classification:** {r.classification}: {r.evidence_note}  "]
    x = dd[(dd.metric == r.metric) & (dd.start_date == r.start_date)] if len(dd) else dd
    if len(x):
        lines.append("**Potential dimensions to investigate** (largest contribution to the deviation):")
        for dim, g in x.groupby("dimension", sort=False):
            t = g.iloc[0]
            rate = f", rate {t.baseline_rate:.1%} → {t.current_rate:.1%}" if pd.notna(t.baseline_rate) else ""
            lines.append(f"- {dim} = **{t.dimension_value}** ({t.share_of_deviation:.0%} of the deviation{rate})")
    return "\n".join(lines)


def card_segment(r, sd):
    lines = [f"**Metric:** {r.display}, segment {r.dimension} = **{r.dimension_value}**  ",
             f"**Window:** {r.start_date} → {r.end_date} ({r.weeks} wk)  ",
             f"**Expected:** {r.expected:.1%}  ", f"**Actual:** {r.actual:.1%}  ",
             f"**Deviation:** {r.deviation:+.1%} (volume {r.volume:,.0f}, |z| {r.max_abs_z:.1f})  ",
             f"**Severity:** {r.severity}  "]
    x = sd[(sd.segment == f"{r.dimension}={r.dimension_value}") & (sd.start_date == r.start_date)] if len(sd) else sd
    if len(x):
        lines.append("**Potential dimensions to investigate** (inside this segment; share of the deviation):")
        for dim, g in x.groupby("dimension", sort=False):
            parts = [f"{t.dimension_value} ({t.share_of_deviation:.0%}; {t.baseline_rate:.1%} → {t.current_rate:.1%})"
                     for t in g.itertuples() if pd.notna(t.baseline_rate)]
            lines.append(f"- {dim}: " + ", ".join(parts))
    lines.append("*This localises the drop. It does not prove the cause.*")
    return "\n".join(lines)


def evaluate(inc, seg, raw_hits):
    p = ROOT / "data" / "ground_truth" / "scenarios.json"
    if not p.exists():
        return "_Ground truth not available._"
    gt = json.loads(p.read_text())
    s2a, s2b = pd.Timestamp(gt["S2_START"]).date(), pd.Timestamp(gt["S2_END"]).date()
    bot, dup = pd.Timestamp(gt["DQ_BOT_SPIKE_DAY"]).date(), pd.Timestamp(gt["S4_DUP_DAY"]).date()
    states = set(gt["S2_STATES"])
    def ov(df, a, b):
        return (df.start_date <= b) & (df.end_date >= a) if len(df) else pd.Series(dtype=bool)
    s2_vals = states | {gt["S2_APP_VERSION_BAD"], "mobile_app", "UPI"}
    s2_seg = seg[ov(seg, s2a, s2b) & seg.dimension_value.isin(s2_vals)
                 & seg.metric.isin(["payment_success_rate", "checkout_conversion"])] if len(seg) else seg
    found = sorted(set(s2_seg.dimension_value)) if len(s2_seg) else []
    rows = [
        ("S2 UPI failures in 3 states (segment scan)", f"{s2a}..{s2b}", bool(len(s2_seg)), ", ".join(found) or "-"),
        ("S2 visible in NATIONAL payment success?", f"{s2a}..{s2b}",
         bool((ov(inc, s2a, s2b) & (inc.metric == "payment_success_rate")).any()), "averages hide segment problems"),
        ("Bot spike -> sessions, classified data_quality", str(bot),
         bool((ov(inc, bot, bot) & (inc.metric == "sessions_incl_bots") & (inc.classification == "data_quality")).any()), ""),
        ("S4 re-sent batch caught in RAW layer", str(dup), bool((raw_hits.date_day.dt.date == dup).any()) if len(raw_hits) else False, ""),
        ("S4 absent from governed net revenue", str(dup), not bool((ov(inc, dup, dup) & (inc.metric == "net_revenue")).any()),
         "de-dup in staging works"),
    ]
    tab = pd.DataFrame(rows, columns=["planted event", "when", "detected / true", "note"])
    fp_seg = seg[~(ov(seg, s2a, s2b) & seg.dimension_value.isin(s2_vals))] if len(seg) else seg
    biz = inc[inc.classification == "business_signal"]
    return (md_table(tab) + f"\n\n* Top-line incidents classified `business_signal`: **{len(biz)}**. Segment incidents "
            f"outside the planted S2 window/segments: **{len(fp_seg)}**. Treat these as the false-positive budget. "
            "Each needs triage, not an automatic page.\n* S3 (VoltEdge refund drift) is a **slow trend**, not an "
            "anomaly. A day-over-day detector is the wrong tool for it, so it is caught by trend monitoring "
            "(sql/analysis/13_brand_refund_trend.sql) instead.")


def main():
    d = load_daily()
    scores = score_topline(d)
    inc = classify(build_incidents(scores, d))
    seg, segz = segment_scan(d)
    raw_hits = raw_layer_scan()
    focus = inc[~inc.classification.isin(["expected_seasonal", "one_off_outlier"])]
    dd = drilldown(focus)
    sd = segment_drill(seg) if len(seg) else pd.DataFrame()
    write_df(scores, "anomaly_scores")
    write_df(inc, "anomaly_alerts")
    write_df(seg if len(seg) else pd.DataFrame({"metric": []}), "anomaly_segment_alerts")
    write_df(dd if len(dd) else pd.DataFrame({"metric": []}), "anomaly_drilldown")
    write_df(sd if len(sd) else pd.DataFrame({"metric": []}), "anomaly_segment_drilldown")
    order = {"High": 0, "Medium": 1, "Low": 2}
    top = focus.assign(o=focus.severity.map(order), a=-focus.est_impact_inr.abs()).sort_values(["o", "a"]).head(6)
    seg_top = seg.assign(o=seg.severity.map(order)).sort_values(["o", "deviation"]).head(8) if len(seg) else seg
    summary = inc.groupby(["metric", "classification"]).size().unstack(fill_value=0).reset_index() if len(inc) else inc
    txt = f"""# Anomaly Detection Report

**Level 1: top-line governed metrics.** Same-weekday robust z (median over 8 weeks, sale days masked out of
the baseline, empirical noise scale), an STL residual cross-check, and a quasi-binomial z for rates.
The thresholds are |z| ≥ {Z_THR} **and** |deviation| ≥ {MIN_DEV:.0%}. Both conditions must hold, because
statistical significance without business size is noise.
**Level 2: weekly segment scan for ratio metrics.** Every dimension value with at least {SEG_MIN_DEN}
weekly attempts is checked, with thresholds z ≤ −{SEG_Z} and deviation ≤ −{SEG_DEV:.0%}.

## Level-1 incident summary
{md_table(summary) if len(summary) else '_none_'}

## Top Level-1 incidents (excluding expected festive peaks)

{chr(10).join(card_topline(r, dd) + chr(10) + chr(10) + '---' + chr(10) for r in top.itertuples()) or '_none_'}

## Level-2 segment incidents (most severe first)

{chr(10).join(card_segment(r, sd) + chr(10) + chr(10) + '---' + chr(10) for r in seg_top.itertuples()) if len(seg_top) else '_none_'}

## Raw-layer scan (issues the governed layer has already neutralised)
{md_table(raw_hits[['date_day', 'actual', 'expected', 'dup_rate']]) if len(raw_hits) else '_none_'}

## Evaluation against the planted ground truth
{evaluate(inc, seg, raw_hits)}

## What this system can and cannot tell you
* **It can tell you** that a metric is unusual given its own weekday pattern and its volume, how big and
  how long the gap is, and which segments carry it.
* **It cannot tell you why.** "Payment success collapsed for app users in Bihar/UP/WB after 12 Nov"
  is a lead for engineering. It becomes a cause only when release notes, gateway logs, or a rollback
  confirm it.
* Festive peaks are labelled `expected_seasonal` instead of alerted, and they are masked out of the
  baselines so that the week after Diwali isn't judged against Diwali.
"""
    write("anomaly_detection.md", txt)
    print(inc.classification.value_counts().to_dict() if len(inc) else {}, "segment incidents:", len(seg))
    if len(seg):
        print(seg[["metric", "dimension", "dimension_value", "start_date", "end_date", "deviation"]].to_string())


if __name__ == "__main__":
    main()
