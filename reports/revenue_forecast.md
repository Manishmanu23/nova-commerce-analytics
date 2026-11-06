# Net Revenue Forecast (next 13 weeks)

Backtest: rolling origin over the last 26 weeks, horizons 1-13. **Selected model: `ets_damped_log`.**

| model | WAPE | bias |
|---|---|---|
| ets_damped_log | 0.1582 | -0.1334 |
| seasonal_naive_x_growth | 0.1685 | -0.05833 |
| mean_4w | 0.1754 | -0.1633 |
| naive | 0.178 | -0.1352 |

13-week total forecast: **₹22,665,914** (80% interval of weekly values from the backtest error
quantiles; summed P10 ₹21,499,436 to P90 ₹32,580,940).

> **Label: FORECAST.** It is not a target or a commitment. It assumes no new deep-discount campaign, a
> festive calendar like last year's, and no change in the app funnel. WAPE tells you how wrong this
> method has typically been on this data. The seasonal-naive model depends on a single prior year, which
> is thin evidence for festive timing, since Diwali moves between October and November.
> **Should NOT be used** for inventory buying at SKU level. It is an aggregate planning input.
