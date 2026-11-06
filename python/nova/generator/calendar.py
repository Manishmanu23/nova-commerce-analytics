"""Demand calendar: trend x weekly seasonality x Indian festive/sale calendar."""
from datetime import date, timedelta

import numpy as np
import pandas as pd

# (name, anchor date, days before, days after, multiplier)
FESTIVALS = [
    ("Republic Day Sale", date(2024, 1, 26), 3, 1, 1.35),
    ("Holi", date(2024, 3, 25), 3, 0, 1.15),
    ("End of Season Sale", date(2024, 7, 5), 3, 4, 1.30),
    ("Independence Day Sale", date(2024, 8, 15), 3, 1, 1.30),
    ("Big Festive Sale", date(2024, 10, 3), 0, 8, 1.90),
    ("Diwali", date(2024, 11, 1), 5, 2, 2.30),
    ("Year End Sale", date(2024, 12, 25), 2, 6, 1.25),
    ("Republic Day Sale", date(2025, 1, 26), 3, 1, 1.35),
    ("Holi", date(2025, 3, 14), 3, 0, 1.15),
    ("End of Season Sale", date(2025, 7, 4), 3, 4, 1.30),
    ("Independence Day Sale", date(2025, 8, 15), 3, 1, 1.30),
    ("Big Festive Sale", date(2025, 9, 23), 0, 8, 1.90),
    ("Diwali", date(2025, 10, 20), 5, 2, 2.30),
    ("Year End Sale", date(2025, 12, 25), 2, 6, 1.25),
]
WEEKDAY_MULT = np.array([0.95, 0.96, 0.97, 0.98, 1.02, 1.10, 1.08])  # Mon..Sun


def festival_lookup(days: pd.DatetimeIndex):
    name = np.array([""] * len(days), dtype=object)
    mult = np.ones(len(days))
    d0 = days[0].date()
    for fname, anchor, before, after, m in FESTIVALS:
        for k in range(-before, after + 1):
            d = anchor + timedelta(days=k)
            i = (d - d0).days
            if 0 <= i < len(days) and m > mult[i]:
                mult[i] = m
                name[i] = fname
    return name, mult


def demand_index(days: pd.DatetimeIndex) -> np.ndarray:
    t = np.arange(len(days)) / len(days)
    trend = 1.0 + 0.35 * t
    weekly = WEEKDAY_MULT[days.dayofweek.values]
    _, fest = festival_lookup(days)
    return trend * weekly * fest


def dates_table(days: pd.DatetimeIndex) -> pd.DataFrame:
    name, mult = festival_lookup(days)
    fy = np.where(days.month >= 4, days.year + 1, days.year)
    fq = ((days.month - 4) % 12) // 3 + 1
    return pd.DataFrame({
        "date_day": days.strftime("%Y-%m-%d"),
        "festival_name": name,
        "is_sale_period": (mult > 1.0).astype(int),
        "fiscal_year": ["FY" + str(y) for y in fy],
        "fiscal_quarter": ["Q" + str(q) for q in fq],
    })
