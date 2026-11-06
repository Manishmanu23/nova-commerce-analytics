from datetime import date

from nova.copilot.planner import plan


def test_last_month_is_latest_complete_month():
    p = plan("Why did revenue decline last month?", data_end=date(2025, 12, 31))
    assert p.metric == "net_revenue" and p.period_b == (date(2025, 12, 1), date(2025, 12, 31))
    assert p.period_a == (date(2025, 11, 1), date(2025, 11, 30)) and p.premise == "decline"


def test_ungoverned_metric_refused():
    assert plan("What is our NPS?").intent == "refuse"
    assert plan("What was GMV last month?").intent == "refuse"


def test_quarter_comparison():
    p = plan("Compare contribution margin Q3 2025 vs Q2 2025")
    assert p.metric == "contribution_margin"
    assert p.period_b[0] == date(2025, 7, 1) and p.period_a[0] == date(2025, 4, 1)


def test_out_of_window_refused():
    assert plan("What was revenue in March 2023?").intent == "refuse"
