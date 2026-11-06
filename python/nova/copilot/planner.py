"""
Question -> analysis plan. Deterministic first (auditable); an LLM may only choose FROM the catalogue.
If the requested metric is not governed, the plan is a refusal with the closest governed alternatives.
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

SYNONYMS = [  # order matters: most specific first
    (r"contribution margin after marketing|cm after marketing", "contribution_margin_after_marketing"),
    (r"contribution margin %|cm ?%|margin rate|margin percent", "cm_pct"),
    (r"contribution margin|contribution|\bcm\b|profitab|margin", "contribution_margin"),
    (r"gross profit", "gross_profit"), (r"gross revenue", "gross_revenue"),
    (r"net revenue|revenue|sales", "net_revenue"),
    (r"checkout conversion|checkout", "checkout_conversion_rate"),
    (r"conversion", "conversion_rate"), (r"payment (success|failure|failures)|payments? fail", "payment_success_rate"),
    (r"refund|return", "refund_rate"), (r"\baov\b|average order value|basket", "aov"),
    (r"blended cac", "blended_cac"), (r"\bcac\b|acquisition cost", "cac"), (r"\broas\b|return on ad", "roas"),
    (r"new customers|acquisition", "new_customers"), (r"\borders?\b", "orders"),
    (r"revenue per visitor|rpv", "revenue_per_visitor"), (r"churn", "churn_rate_90d"),
    (r"repeat", "repeat_purchase_rate_90d"), (r"\bltv\b|lifetime value", "ltv_180d_cm"),
]
UNGOVERNED = {r"\bnps\b|net promoter": ["(no governed equivalent; NPS is not in the warehouse)"],
              r"\bgmv\b": ["gross_revenue", "net_revenue"], r"\bdau\b|\bmau\b|active users": ["conversion_rate"],
              r"ebitda|net profit|\bpat\b": ["contribution_margin_after_marketing"],
              r"inventory|stock": ["(inventory data is not in this platform)"]}
MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m} | \
         {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}


@dataclass
class Plan:
    intent: str                      # explain_change | value | forecast | refuse
    metric: str | None = None
    period_a: tuple | None = None
    period_b: tuple | None = None
    notes: list = field(default_factory=list)
    refusal: str | None = None
    premise: str | None = None       # "decline" / "increase" if the question asserts a direction


def month_bounds(y, m):
    return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])


def prev_month(y, m):
    return (y - 1, 12) if m == 1 else (y, m - 1)


def plan(question: str, data_end: date = date(2025, 12, 31)) -> Plan:
    q = question.lower()
    for pat, alts in UNGOVERNED.items():
        if re.search(pat, q):
            return Plan("refuse", refusal=f"'{re.search(pat, q).group(0)}' is not a governed metric. "
                                          f"Closest governed alternatives: {', '.join(alts)}.")
    metric = next((m for pat, m in SYNONYMS if re.search(pat, q)), None)
    if metric is None:
        return Plan("refuse", refusal="I could not map this question to a governed metric. Ask about one of the "
                                      "metrics in the catalogue (e.g. net revenue, contribution margin, conversion).")
    if re.search(r"forecast|next quarter|next month|will .* be|predict", q):
        return Plan("forecast", metric=metric, notes=["forecast requested"])
    premise = "decline" if re.search(r"declin|drop|fall|fell|down|decreas|lower", q) else (
        "increase" if re.search(r"increas|grow|rise|rose|up\b|higher", q) else None)
    # ---- periods
    ly, lm = data_end.year, data_end.month
    mq = re.search(r"q([1-4])\s*(20\d\d)", q)
    mm = re.findall(r"\b(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\w*\s*(20\d\d)?", q)
    if "last week" in q:
        b = (data_end - timedelta(days=6), data_end)
        a = (b[0] - timedelta(days=7), b[1] - timedelta(days=7))
    elif mq:
        qi, y = int(mq.group(1)), int(mq.group(2))
        b = (date(y, 3 * qi - 2, 1), month_bounds(y, 3 * qi)[1])
        pq, py = (qi - 1, y) if qi > 1 else (4, y - 1)
        a = (date(py, 3 * pq - 2, 1), month_bounds(py, 3 * pq)[1])
        m2 = re.findall(r"q([1-4])\s*(20\d\d)", q)
        if len(m2) >= 2:
            (q1, y1), (q2, y2) = [(int(x), int(y)) for x, y in m2[:2]]
            b = (date(y1, 3 * q1 - 2, 1), month_bounds(y1, 3 * q1)[1])
            a = (date(y2, 3 * q2 - 2, 1), month_bounds(y2, 3 * q2)[1])
    elif mm:
        name, yr = mm[0]
        m = MONTHS[name[:3]] if name[:3] in MONTHS else MONTHS[name]
        y = int(yr) if yr else (ly if m <= lm else ly - 1)
        b = month_bounds(y, m)
        a = month_bounds(*prev_month(y, m))
    else:   # default: "last month" = latest complete month in the data
        b = month_bounds(ly, lm)
        a = month_bounds(*prev_month(ly, lm))
    if b[1] > data_end or b[0] < date(2024, 1, 1):
        return Plan("refuse", metric=metric, refusal=f"The requested period is outside the governed data window "
                                                      f"(2024-01-01 to {data_end}).")
    intent = "explain_change" if re.search(r"why|driv|what happened|explain|cause|compare|trend|change", q) else "value"
    return Plan(intent, metric, a, b, premise=premise)
