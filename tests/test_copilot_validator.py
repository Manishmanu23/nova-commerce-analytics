"""The grounding validator is a safety control: test it like one (no database needed)."""
from nova.copilot.tools import Evidence
from nova.copilot.validator import validate

EV = [Evidence("E1", "compare_periods", {}, {"value_a": 3467658.0, "value_b": 3811603.0, "pct_change": 0.0992},
               ["₹3,467,658", "₹3,811,603", "+9.9%"])]
CAT = {"net_revenue"}


def test_grounded_answer_passes():
    ok, probs = validate("Net revenue rose from ₹3,467,658 to ₹3,811,603 (+9.9%) [E1].", EV, CAT)
    assert ok, probs


def test_invented_number_rejected():
    ok, probs = validate("Net revenue rose 14% to ₹4,000,000 [E1].", EV, CAT)
    assert not ok and any("ungrounded" in p for p in probs)


def test_unknown_metric_rejected():
    ok, probs = validate("The customer_joy_index improved [E1].", EV, CAT)
    assert not ok


def test_missing_citation_rejected():
    ok, probs = validate("Net revenue was ₹3,811,603.", EV, CAT)
    assert not ok


def test_methodology_constants_exempt():
    ok, probs = validate("Using the 90-day definition, net revenue rose 9.9% [E1].", EV, CAT)
    assert ok, probs
