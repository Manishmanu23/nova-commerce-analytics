from nova.simulator.engine import Baseline, Scenario, project

B = Baseline(base_customers=3000, churn_m=0.15, orders_per_customer=0.6, aov_gross=2200, discount_rate=0.03,
             refund_rate=0.06, cogs_pct=0.65, variable_cost_per_order=150, marketing_spend=250000, acq_spend=240000,
             cac=750, organic_new=120, sd={})


def test_baseline_is_stable_and_labelled_elsewhere():
    r = project(B, Scenario())
    assert len(r) == 12 and (r.net_revenue > 0).all()


def test_better_retention_grows_base():
    a = project(B, Scenario()).base_customers.iat[-1]
    b = project(B, Scenario(retention_pp=2)).base_customers.iat[-1]
    assert b > a


def test_discount_cut_raises_net_revenue_when_volume_unchanged():
    a = project(B, Scenario()).net_revenue.sum()
    b = project(B, Scenario(discount_pp=-1)).net_revenue.sum()
    assert b > a
