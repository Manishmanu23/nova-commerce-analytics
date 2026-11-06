"""
Grounding validator: the last line of defence against hallucinated numbers and metrics.

Rules
  1. Every numeric token in the answer must match a number that appears in the evidence (display strings or
     raw values under standard roundings). Years, dates, evidence ids and small counts (<= 10) are exempt.
  2. Every snake_case metric name mentioned must exist in the certified catalogue.
  3. Every paragraph that contains a number must cite at least one evidence id [E#].
If any rule fails, the answer is rejected and a deterministic, template answer is shown instead.
"""
from __future__ import annotations

import re

NUM = re.compile(r"(?<![A-Za-z#E])[-+]?₹?\d[\d,]*(?:\.\d+)?(?:pp|%|x)?")
SNAKE = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b")


def _norm(tok: str) -> str:
    return tok.replace("₹", "").replace(",", "").replace("+", "").lstrip("-")


def allowed_numbers(evidence) -> set[str]:
    """Numbers the answer may use: tokens from evidence DISPLAY strings (primary), plus raw evidence values at
    1-2 decimals (x100 for ratios) and integers for large values. Deliberately NOT every possible rounding:
    a permissive allow-list would let '12%' slip through just because some ratio happens to be 0.12."""
    out = set()

    def add_display(v):
        if isinstance(v, str):
            for t in NUM.findall(v):
                out.add(_norm(t).rstrip("%px"))
        elif isinstance(v, (list, tuple)):
            for x in v:
                add_display(x)

    def add_raw(v):
        if isinstance(v, bool) or v is None:
            return
        if isinstance(v, (int, float)):
            for f in (1, 2):
                out.add(_norm(f"{v:.{f}f}"))
                if abs(v) <= 1.5:
                    out.add(_norm(f"{v * 100:.{f}f}"))
            if abs(v) >= 100 or float(v).is_integer():
                out.add(_norm(f"{v:.0f}"))
        elif isinstance(v, str):
            add_display(v)
        elif isinstance(v, dict):
            for x in v.values():
                add_raw(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                add_raw(x)
    for e in evidence:
        add_display(e.display)
        add_raw(e.data)
    return out


EXEMPT = re.compile(r"/\s*100\b|\b\d+-(?:day|week|month|year)s?\b|\bQ[1-4]\b|\bv?\d+\.\d+\.\d+\b|\[E\d+\]|\b20\d\d-\d\d-\d\d\b")


def validate(answer: str, evidence, catalog_names: set[str]) -> tuple[bool, list[str]]:
    """Returns (ok, problems). Methodology constants ("90-day"), dates, versions and evidence ids are exempt."""
    problems = []
    raw_answer = answer
    answer = EXEMPT.sub(" ", answer)
    ok_nums = allowed_numbers(evidence)
    for tok in NUM.findall(answer):
        core = _norm(tok).rstrip("%px")
        if not core or re.fullmatch(r"20\d\d", core) or (core.isdigit() and int(core) <= 10):
            continue
        if core not in ok_nums:
            problems.append(f"ungrounded number: {tok}")
    ok_snake = catalog_names | {"customer_type", "device_type", "payment_method", "app_version", "traffic_channel",
                                "order_channel", "city_tier", "is_refund_mature", "mobile_app", "mobile_web",
                                "paid_search", "paid_social", "payment_failed", "upi_intent_launch_failed",
                                "business_signal", "data_quality", "expected_seasonal", "checkout_conversion",
                                "sessions_incl_bots"}
    for s in set(SNAKE.findall(answer)):
        if s not in ok_snake:
            problems.append(f"unknown metric/field name: {s}")
    for para in [p for p in raw_answer.split("\n\n") if NUM.search(EXEMPT.sub(" ", p))]:
        if not re.search(r"\[E\d+\]", para) and any(
                _norm(t).rstrip("%px") not in ("",) and not re.fullmatch(r"20\d\d", _norm(t))
                and not (_norm(t).isdigit() and int(_norm(t)) <= 10) for t in NUM.findall(EXEMPT.sub(" ", para))):
            problems.append("paragraph with numbers but no evidence citation")
            break
    return (not problems), problems
