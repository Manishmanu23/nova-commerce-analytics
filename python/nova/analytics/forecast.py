"""
Weekly net-revenue forecast (13 weeks) with an honest backtest.

Candidates (simple -> less simple): naive, 4-week mean, seasonal-naive x YoY growth, damped-trend ETS on log.
Model choice = lowest WAPE over a rolling-origin backtest of the last 26 weeks (1-13 weeks ahead).
Intervals = empirical quantiles of backtest errors by horizon (no normality assumption).
Everything written here is labelled value_type = 'forecast'.
"""
import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from nova.common.db import read_sql, write_df
from nova.common.report import md_table

H = 13


def weekly():
    d = read_sql("select date_day, net_revenue from metrics.metrics_daily order by 1")
    d["date_day"] = pd.to_datetime(d.date_day)
    w = d.set_index("date_day").net_revenue.astype(float).resample("W-SUN").sum()
    return w.iloc[1:-1] if w.index[-1] > d.date_day.max() else w.iloc[1:]


def f_naive(y, h):
    return np.repeat(y.iloc[-1], h)


def f_mean4(y, h):
    return np.repeat(y.iloc[-4:].mean(), h)


def f_snaive(y, h):
    if len(y) < 60:
        return f_mean4(y, h)
    growth = y.iloc[-8:].sum() / y.iloc[-60:-52].sum()
    return y.iloc[-52:-52 + h].to_numpy() * growth


def f_ets(y, h):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = ExponentialSmoothing(np.log(y), trend="add", damped_trend=True).fit()
    return np.exp(m.forecast(h)).to_numpy()


MODELS = {"naive": f_naive, "mean_4w": f_mean4, "seasonal_naive_x_growth": f_snaive, "ets_damped_log": f_ets}


def backtest(y):
    rows = []
    for origin in range(len(y) - 26 - H, len(y) - H + 1):
        train, test = y.iloc[:origin], y.iloc[origin:origin + H]
        for name, f in MODELS.items():
            fc = f(train, H)[:len(test)]
            for h, (a, p) in enumerate(zip(test.to_numpy(), fc), 1):
                rows.append(dict(model=name, origin=y.index[origin - 1], h=h, actual=a, forecast=p))
    return pd.DataFrame(rows)


def main() -> str:
    y = weekly()
    bt = backtest(y)
    score = bt.groupby("model").apply(lambda g: pd.Series(dict(
        WAPE=(g.actual - g.forecast).abs().sum() / g.actual.sum(),
        bias=(g.forecast - g.actual).sum() / g.actual.sum())), include_groups=False).sort_values("WAPE")
    best = score.index[0]
    fc = MODELS[best](y, H)
    err = bt[bt.model == best].assign(ratio=lambda g: g.actual / g.forecast)
    q = err.groupby("h").ratio.quantile([0.1, 0.9]).unstack()
    idx = pd.date_range(y.index[-1] + pd.Timedelta(weeks=1), periods=H, freq="W-SUN")
    out = pd.concat([
        pd.DataFrame({"week": y.index, "value_type": "actual", "p50": y.to_numpy(), "p10": np.nan, "p90": np.nan}),
        pd.DataFrame({"week": idx, "value_type": "forecast", "p50": fc, "p10": fc * q[0.1].to_numpy(),
                      "p90": fc * q[0.9].to_numpy()})])
    out["model"] = best
    write_df(out, "revenue_forecast")
    f13 = out[out.value_type == "forecast"]
    return f"""# Net Revenue Forecast (next {H} weeks)

Backtest: rolling origin over the last 26 weeks, horizons 1-{H}. **Selected model: `{best}`.**

{md_table(score.reset_index())}

13-week total forecast: **₹{f13.p50.sum():,.0f}** (80% interval of weekly values from the backtest error
quantiles; summed P10 ₹{f13.p10.sum():,.0f} to P90 ₹{f13.p90.sum():,.0f}).

> **Label: FORECAST.** It is not a target or a commitment. It assumes no new deep-discount campaign, a
> festive calendar like last year's, and no change in the app funnel. WAPE tells you how wrong this
> method has typically been on this data. The seasonal-naive model depends on a single prior year, which
> is thin evidence for festive timing, since Diwali moves between October and November.
> **Should NOT be used** for inventory buying at SKU level. It is an aggregate planning input.
"""
