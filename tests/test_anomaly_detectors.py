import numpy as np
import pandas as pd

from nova.anomaly.detectors import rate_binomial_z, seasonal_robust_z


def _series(n=200, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    weekly = np.array([1, 1, 1, 1, 1.05, 1.2, 1.15])[idx.dayofweek]
    return pd.Series(1000 * weekly * rng.lognormal(0, 0.05, n), index=idx)


def test_spike_detected_and_weekday_pattern_not_flagged():
    s = _series()
    s.iloc[150] *= 1.6
    z = seasonal_robust_z(s)
    assert z.z.iloc[150] > 4
    assert (z.z.drop(z.index[150]).abs() > 4).mean() < 0.02   # weekly seasonality is not an anomaly


def test_rate_test_is_volume_aware():
    """The same -15% relative drop is noise on 100 sessions and an incident on 50,000."""
    idx = pd.date_range("2024-01-01", periods=120, freq="D")
    for n, expect_alert in [(100, False), (50_000, True)]:
        den = pd.Series(float(n), index=idx)
        num = den * 0.04
        num.iloc[100] = n * 0.034
        z = rate_binomial_z(num, den).z.iloc[100]
        assert (abs(z) > 4) == expect_alert
