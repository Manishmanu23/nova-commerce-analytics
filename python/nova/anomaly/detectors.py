"""
Interpretable anomaly detectors, simplest first.

1. seasonal_robust_z : expected = median of the same weekday over the previous 8 weeks
                       (sale/festival days are masked out of the baseline so Diwali doesn't inflate "normal").
                       Noise scale = 1.4826 x trailing median |relative deviation| (empirical, adapts to volume).
2. stl_residual_z    : STL (weekly period, robust) residual z - an independent cross-check for value metrics.
3. rate_binomial_z   : for RATIO metrics with count denominators (sessions, attempts). Volume-aware:
                       z = (p_obs - p_exp) / sqrt(p_exp(1-p_exp)/n), divided by sqrt(phi) where phi is the
                       estimated over-dispersion (real data varies more than a pure binomial).

Why not Isolation Forest / LSTM first? Stakeholders must understand WHY an alert fired
("22% below the usual Tuesday"). A black-box score is hard to act on and hard to trust. We only reach
for ML if these baselines demonstrably miss things (see the evaluation in reports/anomaly_detection.md).
"""
import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import STL

MAD_K = 1.4826
CHI2_1_MEDIAN = 0.4549


def _lags(s: pd.Series, season: int, n: int, mask: pd.Series | None) -> pd.DataFrame:
    base = s.where(~mask) if mask is not None else s
    return pd.concat({k: base.shift(season * k) for k in range(1, n + 1)}, axis=1)


def seasonal_robust_z(s: pd.Series, season: int = 7, n_lags: int = 8, noise_window: int = 91,
                      mask: pd.Series | None = None) -> pd.DataFrame:
    lags = _lags(s, season, n_lags, mask)
    expected = lags.median(axis=1).where(lags.notna().sum(axis=1) >= n_lags // 2)
    rel = s / expected.replace(0, np.nan) - 1
    clean_rel = rel.where(~mask) if mask is not None else rel
    noise = MAD_K * clean_rel.abs().rolling(noise_window, min_periods=max(4, noise_window // 4)).median().shift(1)
    return pd.DataFrame({"actual": s, "expected": expected, "deviation": rel, "z": rel / noise})


def stl_residual_z(s: pd.Series, period: int = 7, window: int = 91) -> pd.DataFrame:
    s = s.astype(float).interpolate(limit_direction="both")
    res = STL(s, period=period, robust=True).fit()
    resid = res.resid
    scale = MAD_K * resid.abs().rolling(window, min_periods=28).median().shift(1)
    return pd.DataFrame({"expected": res.trend + res.seasonal, "z": resid / scale})


def rate_binomial_z(num: pd.Series, den: pd.Series, season: int = 7, n_lags: int = 8,
                    mask: pd.Series | None = None, phi_window: int = 91) -> pd.DataFrame:
    """Expected rate = pooled rate of the same weekday over previous weeks (sum num / sum den)."""
    n_m = num.where(~mask) if mask is not None else num
    d_m = den.where(~mask) if mask is not None else den
    lag_num = pd.concat({k: n_m.shift(season * k) for k in range(1, n_lags + 1)}, axis=1).sum(axis=1, min_count=4)
    lag_den = pd.concat({k: d_m.shift(season * k) for k in range(1, n_lags + 1)}, axis=1).sum(axis=1, min_count=4)
    p_exp = lag_num / lag_den
    p_obs = num / den.replace(0, np.nan)
    z_raw = (p_obs - p_exp) / np.sqrt(p_exp * (1 - p_exp) / den.replace(0, np.nan))
    zc = z_raw.where(~mask) if mask is not None else z_raw
    phi = (zc ** 2).rolling(phi_window, min_periods=20).median().shift(1) / CHI2_1_MEDIAN
    phi = phi.clip(lower=1.0).fillna(1.0)
    return pd.DataFrame({"actual": p_obs, "expected": p_exp, "deviation": p_obs / p_exp - 1,
                         "z": z_raw / np.sqrt(phi), "phi": phi, "denominator": den})
