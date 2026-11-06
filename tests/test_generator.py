"""Generator must be deterministic and must actually contain the defects we claim to handle."""
import pandas as pd
import pytest

from nova.generator import run


@pytest.fixture(scope="module")
def landing(tmp_path_factory):
    out = tmp_path_factory.mktemp("gen") / "landing"
    run.main(["--customers", "800", "--session-mult", "0.05", "--out", str(out), "--seed", "123"])
    return out


def test_all_tables_written(landing):
    names = {p.stem for p in (landing / "2026-01-01").glob("*.csv")}
    expected = {"customers", "orders", "order_items", "products", "payments", "refunds", "marketing_campaigns",
                "marketing_spend", "web_sessions", "funnel_events", "customer_support", "experiments",
                "experiment_assignments", "geography", "dates", "subscriptions"}
    assert expected <= names


def test_deterministic(tmp_path, landing):
    out2 = tmp_path / "landing"
    run.main(["--customers", "800", "--session-mult", "0.05", "--out", str(out2), "--seed", "123"])
    a = pd.read_csv(landing / "2026-01-01" / "orders.csv")
    b = pd.read_csv(out2 / "2026-01-01" / "orders.csv")
    assert a.equals(b)


def test_defects_present(landing):
    o = pd.read_csv(landing / "2026-01-01" / "orders.csv")
    assert o.order_id.duplicated().any(), "retry duplicates expected"
    assert (o.order_ts.str.startswith("1970")).any() or (o.order_ts.str.startswith("2031")).any()
    p = pd.read_csv(landing / "2026-01-01" / "products.csv")
    assert p.category.nunique() > 6, "messy category labels expected"
    r = pd.concat(pd.read_csv(f) for f in landing.glob("*/refunds.csv"))
    assert (r.refund_amount < 0).any(), "sign-flipped refunds expected"
