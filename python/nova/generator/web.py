"""Web/app traffic: non-converting sessions (vectorised) + funnel events + bot spike (DQ defect)."""
import numpy as np
import pandas as pd

from . import scenarios as S

CR = {"mobile_app": 0.045, "mobile_web": 0.022, "desktop": 0.032}   # target session conversion
MAX_STEP_P = {"mobile_app": [0.56, 0.28, 0.16], "mobile_web": [0.68, 0.22, 0.10], "desktop": [0.61, 0.25, 0.14]}
NC_TRAFFIC = np.array(["direct", "organic_search", "paid_search", "paid_social", "email", "push", "referral", "affiliate"])
NC_TRAFFIC_P = [0.24, 0.30, 0.15, 0.15, 0.05, 0.03, 0.03, 0.05]
CODE = {"paid_search": "PSE", "paid_social": "PSO", "affiliate": "AFF", "email": "EML"}


def _browser(rng, device, os_):
    n = len(device)
    out = np.empty(n, dtype=object)
    r = rng.random(n)
    app = device == "mobile_app"
    out[app] = "NovaApp"
    mw = device == "mobile_web"
    out[mw] = np.where(os_[mw] == "ios", "safari", np.where(r[mw] < 0.86, "chrome", "samsung_internet"))
    dk = device == "desktop"
    out[dk] = np.where(os_[dk] == "macos", np.where(r[dk] < 0.6, "safari", "chrome"),
                       np.where(r[dk] < 0.76, "chrome", np.where(r[dk] < 0.93, "edge", "firefox")))
    return out


def _app_version(rng, device, t, off):
    n = len(t)
    r = rng.random(n)
    v = np.where(t < off(pd.Timestamp("2025-07-01").date()), "5.0.4", "5.1.2").astype(object)
    s, e = off(S.S2_START), off(S.S2_END)
    in_bad = (t >= s) & (t < e)
    v[in_bad] = np.where(r[in_bad] < 0.88, S.S2_APP_VERSION_BAD, "5.1.2")
    after = t >= e
    v[after] = np.where(r[after] < 0.85, S.S2_APP_VERSION_FIX, S.S2_APP_VERSION_BAD)
    v[device != "mobile_app"] = None
    return v


def build_sessions(sim, cfg, rng):
    T, off = sim.T, sim.off
    conv = pd.DataFrame(sim.sessions, columns=["sid", "customer_id", "start_t", "device", "os", "geo_idx",
                                               "traffic", "utm", "converting"])
    conv["day"] = conv.start_t.astype(int).clip(0, T - 1)
    cnt = conv.groupby(["day", "device"]).size().reset_index(name="n")
    cnt["lam"] = cnt.n * (1 / cnt.device.map(CR) - 1) * cfg.session_multiplier
    cnt["k"] = rng.poisson(cnt.lam)
    day = np.repeat(cnt.day.values, cnt.k.values)
    dev = np.repeat(cnt.device.values, cnt.k.values).astype(object)
    # DQ defect: bot spike
    nb = int(20000 * cfg.session_multiplier)
    bot = np.zeros(len(day) + nb, bool)
    bot[len(day):] = True
    day = np.concatenate([day, np.full(nb, off(S.DQ_BOT_SPIKE_DAY))])
    dev = np.concatenate([dev, np.array(["desktop"] * nb, dtype=object)])
    N = len(day)
    from .commerce import HOUR_P
    st = day + (rng.choice(24, N, p=HOUR_P) + rng.random(N)) / 24
    C = sim.C
    signed = np.searchsorted(C.signup_t.values, st)
    logged = (rng.random(N) < 0.40) & (signed > 0) & ~bot
    cidx = np.floor(rng.random(N) * np.maximum(signed, 1)).astype(int)
    cust = np.where(logged, C.customer_id.values[cidx], None)
    geo = np.where(logged, C.geo1.values[cidx], rng.choice(len(sim.geo), N, p=sim.geo_p))
    ios_c = np.where(logged, C.ios.values[cidx], rng.random(N) < 0.22)
    os_ = np.where(dev == "desktop", np.where(rng.random(N) < 0.15, "macos", "windows"),
                   np.where(ios_c, "ios", "android")).astype(object)
    os_[bot] = "linux"
    traffic = rng.choice(NC_TRAFFIC, N, p=NC_TRAFFIC_P).astype(object)
    traffic[(traffic == "push") & (dev != "mobile_app")] = "direct"
    traffic[bot] = "direct"
    dates = pd.Timestamp(cfg.start) + pd.to_timedelta(day, unit="D")
    q = (dates.month.values - 1) // 3 + 1
    yr = dates.year.values
    utm = np.full(N, "", dtype=object)
    for ch, code in CODE.items():
        m = traffic == ch
        utm[m] = ["CMP-%s-%dQ%d" % (code, y, qq) for y, qq in zip(yr[m], q[m])]
    blitz = (traffic == "paid_social") & (st >= off(S.S1_START)) & (st < off(S.S1_END) + 1) & (rng.random(N) < 0.45)
    utm[blitz] = S.S1_CAMPAIGN_ID
    step = np.zeros(N, int)
    for d, p in MAX_STEP_P.items():
        m = dev == d
        step[m] = rng.choice(3, m.sum(), p=p)
    step[bot] = 0
    nc = pd.DataFrame({"sid": -np.arange(1, N + 1), "customer_id": cust, "start_t": st, "device": dev, "os": os_,
                       "geo_idx": geo, "traffic": traffic, "utm": utm, "converting": False, "step": step,
                       "bot": bot})
    conv["step"], conv["bot"] = 4, False
    allS = pd.concat([conv.drop(columns="day"), nc], ignore_index=True).sort_values("start_t", kind="stable")
    allS["session_id"] = np.arange(1, len(allS) + 1) + 10_000_000
    idmap = dict(zip(allS.sid[allS.sid > 0], allS.session_id[allS.sid > 0]))
    allS["browser"] = _browser(rng, allS.device.values, allS.os.values)
    allS.loc[allS.bot, "browser"] = "HeadlessChrome"
    allS["app_version"] = _app_version(rng, allS.device.values, allS.start_t.values, off)
    allS["duration_sec"] = np.round(rng.lognormal(4.0 + 0.5 * allS.step.values, 0.7)).astype(int)
    allS.loc[allS.bot, "duration_sec"] = rng.integers(1, 4, allS.bot.sum())
    allS["landing_page"] = rng.choice(["home", "category", "product", "search", "campaign_lp"], len(allS),
                                      p=[0.35, 0.2, 0.25, 0.12, 0.08])
    allS.loc[allS.utm.str.len() > 0, "landing_page"] = "campaign_lp"
    allS["geo_id"] = sim.geo.geo_id.values[allS.geo_idx.values.astype(int)]

    # ---- events
    ce = pd.DataFrame(sim.events, columns=["sid", "ts", "event_name", "product_id"])
    ce["session_id"] = ce.sid.map(idmap)
    ncs = allS[allS.sid < 0]
    pp = sim.prods.popularity.values / sim.prods.popularity.sum()
    parts = [ce[["session_id", "ts", "event_name", "product_id"]]]
    for k, name in enumerate(["product_view", "add_to_cart", "begin_checkout"]):
        m = ncs.step.values >= k
        s = ncs[m]
        ts = s.start_t.values + (k + 1) * rng.uniform(0.5, 3, len(s)) / 1440
        pid = sim.prods.product_id.values[rng.choice(len(pp), len(s), p=pp)] if k < 2 else None
        parts.append(pd.DataFrame({"session_id": s.session_id.values, "ts": ts, "event_name": name,
                                   "product_id": pid}))
    ev = pd.concat(parts, ignore_index=True).sort_values(["ts"], kind="stable")
    ev["event_id"] = np.arange(1, len(ev) + 1)
    return allS, ev, idmap
