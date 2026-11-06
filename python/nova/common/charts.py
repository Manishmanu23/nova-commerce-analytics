"""Static charts for the README / case study (generated from governed tables): python -m nova.common.charts"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from nova.common.db import read_sql  # noqa: E402
from nova.common.report import ROOT  # noqa: E402

OUT = ROOT / "docs" / "images"
C1, C2, C3, GREY = "#1f4e79", "#c0504d", "#f39c12", "#7f7f7f"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 130})


def revenue_cm():
    m = read_sql("select month, net_revenue, cm_pct from metrics.metrics_monthly order by month")
    m["month"] = pd.to_datetime(m.month)
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.bar(m.month, m.net_revenue.astype(float) / 1e5, width=20, color=C1, label="Net revenue (₹ lakh)")
    ax.set_ylabel("₹ lakh")
    ax2 = ax.twinx()
    ax2.plot(m.month, m.cm_pct.astype(float) * 100, color=C2, marker="o", label="CM % of net revenue")
    ax2.set_ylabel("CM %")
    ax2.set_ylim(0, 30)
    ax.axvspan(pd.Timestamp("2025-07-20"), pd.Timestamp("2025-10-31"), color=C3, alpha=0.15)
    ax.text(pd.Timestamp("2025-07-25"), ax.get_ylim()[1] * 0.92, "40%-off\nblitz", fontsize=8)
    ax.set_title("Growth vs profitability: revenue up, contribution margin % diluted (simulated)")
    fig.legend(loc="upper left", bbox_to_anchor=(0.07, 0.88), fontsize=8, frameon=False)
    fig.tight_layout(); fig.savefig(OUT / "01_revenue_vs_cm.png"); plt.close(fig)


def retention():
    r = read_sql("""select acquisition_segment, months_since_first, sum(active_customers)::float / sum(cohort_size) as ret
                    from marts.mart_cohort_retention where cohort_month between '2024-06-01' and '2025-09-01'
                      and months_since_first <= 3 group by 1, 2""")
    p = r.pivot(index="acquisition_segment", columns="months_since_first", values="ret")
    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    for seg, row in p.iterrows():
        hl = seg == "deep_discount_campaign"
        ax.plot(row.index, row.values * 100, marker="o", lw=2.5 if hl else 1.2, color=C2 if hl else GREY,
                label=seg if hl else None)
        ax.text(row.index[-1] + 0.05, row.values[-1] * 100, seg, fontsize=7, color=C2 if hl else GREY, va="center")
    ax.set_xticks([0, 1, 2, 3]); ax.set_xlabel("Months since first order"); ax.set_ylabel("Active customers %")
    ax.set_title("Cohort retention by acquisition segment: deep-discount cohort decays fastest")
    fig.tight_layout(); fig.savefig(OUT / "02_retention_by_segment.png"); plt.close(fig)


def payments_s2():
    q = read_sql("""select date_trunc('week', p.payment_date)::date as wk,
                           case when g.state in ('Uttar Pradesh','Bihar','West Bengal') then g.state else 'Other states' end as st,
                           avg(p.is_success::int) as sr, count(*) n
                    from marts.fct_payments p join marts.dim_geography g using (geo_id)
                    where p.is_prepaid_attempt and p.device_type = 'mobile_app' and p.payment_date between '2025-09-01' and '2025-12-28'
                    group by 1, 2""")
    q["wk"] = pd.to_datetime(q.wk)
    fig, ax = plt.subplots(figsize=(8.5, 3.4))
    for st, g in q.groupby("st"):
        ax.plot(g.wk, g.sr * 100, marker="o", lw=2.2 if st != "Other states" else 1.5,
                color=GREY if st == "Other states" else None, label=st)
    ax.axvspan(pd.Timestamp("2025-11-12"), pd.Timestamp("2025-12-03"), color=C2, alpha=0.1)
    ax.text(pd.Timestamp("2025-11-13"), 45, "app v5.2.0 →\nhotfix 5.2.1", fontsize=8)
    ax.set_ylabel("App payment success %"); ax.set_ylim(35, 100); ax.legend(fontsize=8, frameon=False, ncol=4)
    ax.set_title("Segment anomaly: app payment success collapsed in 3 states (national rate hid it)")
    fig.tight_layout(); fig.savefig(OUT / "03_app_payment_success_by_state.png"); plt.close(fig)


def campaigns():
    c = read_sql("""with sp as (select campaign_id, sum(spend_inr) spend from marts.fct_marketing_spend group by 1)
                    select dc.campaign_name, dc.first_order_discount_pct d, count(*) n,
                           avg(cm_90d) filter (where is_mature_90d) cm90, max(sp.spend) / count(*) cac
                    from marts.mart_customer_ltv l join marts.dim_campaign dc on dc.campaign_id = l.signup_campaign_id
                    join sp on sp.campaign_id = dc.campaign_id group by 1, 2 having count(*) >= 60""")
    fig, ax = plt.subplots(figsize=(7.5, 4))
    col = [C2 if d >= 0.3 else (C3 if d >= 0.2 else C1) for d in c.d.astype(float)]
    ax.scatter(c.cac.astype(float), c.cm90.astype(float), s=c.n.astype(float) / 4, c=col, alpha=0.75)
    lim = max(c.cac.astype(float).max(), c.cm90.astype(float).max()) * 1.1
    ax.plot([0, lim], [0, lim], ls="--", color=GREY, lw=1); ax.text(lim * 0.7, lim * 0.75, "90-day payback line", fontsize=8, color=GREY)
    for r in c.itertuples():
        if r.d >= 0.3:
            ax.annotate("Social Blitz (40% off)", (float(r.cac), float(r.cm90)), xytext=(10, -15), textcoords="offset points", fontsize=8)
    ax.set_xlabel("CAC (₹)"); ax.set_ylabel("90-day CM per customer (₹)")
    ax.set_title("Campaigns: cheapest CAC ≠ best value (bubble = customers)")
    fig.tight_layout(); fig.savefig(OUT / "04_campaign_cac_vs_cm90.png"); plt.close(fig)


def dq():
    d = read_sql("select dimension, score from dq.dq_scorecard where dimension <> 'OVERALL' order by score")
    o = read_sql("select score from dq.dq_scorecard where dimension = 'OVERALL'").score.iat[0]
    fig, ax = plt.subplots(figsize=(6.5, 3))
    ax.barh(d.dimension, d.score.astype(float), color=[C1 if s >= 90 else C3 for s in d.score.astype(float)])
    ax.set_xlim(0, 100); ax.axvline(float(o), color=C2, ls="--"); ax.text(float(o) + 1, -0.6, f"overall {o}", color=C2, fontsize=8)
    ax.set_title("Data Quality Scorecard (warn = known & mitigated defect)")
    fig.tight_layout(); fig.savefig(OUT / "05_dq_scorecard.png"); plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in (revenue_cm, retention, payments_s2, campaigns, dq):
        f()
        print("chart:", f.__name__)


if __name__ == "__main__":
    main()
