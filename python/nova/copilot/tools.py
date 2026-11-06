"""
Read-only, governed tools. They are the ONLY way the Copilot can see data.

* They query only the governed layer: metrics.*, analytics.anomaly_*, analytics.revenue_forecast, dq.*
* Ratios are always recomputed from numerator/denominator components (never averaged).
* Every result is an Evidence object with an id (E1, E2, ...), the exact query arguments and pre-formatted
  display strings. The LLM must cite evidence ids, and the validator checks every number against them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from nova.common.db import read_sql

# metric -> (numerator, denominator or None, unit, source) for DAILY-decomposable metrics
DAILY = {
    "gross_revenue": ("gross_revenue", None, "INR"), "net_revenue": ("net_revenue", None, "INR"),
    "orders": ("orders", None, "count"), "gross_profit": ("gross_profit", None, "INR"),
    "contribution_margin": ("contribution_margin", None, "INR"),
    "contribution_margin_after_marketing": ("contribution_margin_after_marketing", None, "INR"),
    "cm_pct": ("contribution_margin", "net_revenue", "pct"), "aov": ("aov_order_value", "aov_orders", "INR"),
    "conversion_rate": ("purchase_sessions", "sessions", "pct"),
    "checkout_conversion_rate": ("purchase_sessions", "checkout_sessions", "pct"),
    "payment_success_rate": ("successful_payment_attempts", "payment_attempts", "pct"),
    "refund_rate": ("return_refund_amount", "gross_revenue", "pct"),
    "new_customers": ("new_customers", None, "count"), "cac": ("acquisition_spend", "paid_new_customers", "INR"),
    "blended_cac": ("acquisition_spend", "new_customers", "INR"),
    "roas": ("attributed_net_revenue", "marketing_spend", "ratio"),
    "revenue_per_visitor": ("web_app_net_revenue", "sessions", "INR"),
}
# metrics only meaningful at monthly cohort grain (read from metrics_monthly)
MONTHLY_ONLY = {"retention_rate": "active_customers", "churn_rate_90d": "churn_rate_90d",
                "repeat_purchase_rate_90d": "repeat_purchase_rate_90d", "ltv_180d_cm": "ltv_180d_cm"}
# which metrics can be broken down by dimension (components exist in metrics_daily_by_dimension)
DIM_COMPONENTS = {
    "net_revenue": ("net_revenue", None), "gross_revenue": ("gross_revenue", None), "orders": ("orders", None),
    "contribution_margin": ("contribution_margin", None), "aov": ("aov_order_value", "aov_orders"),
    "conversion_rate": ("purchase_sessions", "sessions"),
    "checkout_conversion_rate": ("purchase_sessions", "checkout_sessions"),
    "payment_success_rate": ("successful_payment_attempts", "payment_attempts"),
    "refund_rate": ("return_refund_amount", "gross_revenue"),
}
DIMENSIONS_FOR = {
    "net_revenue": ["channel", "customer_type", "device_type", "state", "category"],
    "gross_revenue": ["channel", "customer_type", "device_type", "category"],
    "orders": ["channel", "customer_type", "device_type", "state"],
    "contribution_margin": ["channel", "customer_type", "device_type", "category"],
    "aov": ["channel", "device_type", "customer_type", "order_channel"],
    "conversion_rate": ["device_type", "traffic_channel", "state", "browser"],
    "checkout_conversion_rate": ["device_type", "app_version", "state", "browser"],
    "payment_success_rate": ["payment_method", "device_type", "app_version", "state"],
    "refund_rate": ["category", "brand", "channel", "payment_method"],
}


def fmt(v, unit):
    if v is None or pd.isna(v):
        return "n/a"
    if unit == "pct":
        return f"{v * 100:.2f}%"
    if unit == "INR":
        return f"₹{v:,.0f}"
    if unit == "ratio":
        return f"{v:.2f}x"
    return f"{v:,.0f}"


def fmt_change(v):
    return "n/a" if v is None or pd.isna(v) else f"{v * 100:+.1f}%"


@dataclass
class Evidence:
    id: str
    tool: str
    args: dict
    data: dict | list
    display: list[str] = field(default_factory=list)


class Tools:
    def __init__(self):
        self._n = 0
        self.catalog = read_sql("select * from metrics.metric_catalog")
        self.bounds = read_sql("select min(date_day) a, max(date_day) b from metrics.metrics_daily").iloc[0]

    def _ev(self, tool, args, data, display):
        self._n += 1
        return Evidence(f"E{self._n}", tool, args, data, display)

    # --------------------------------------------------------------- catalogue
    def list_metrics(self) -> Evidence:
        cat = self.catalog[["metric_name", "display_name", "definition", "unit"]].to_dict("records")
        return self._ev("list_metrics", {}, cat, [c["metric_name"] for c in cat])

    def metric_info(self, metric) -> dict | None:
        r = self.catalog[self.catalog.metric_name == metric]
        return None if r.empty else r.iloc[0].to_dict()

    # --------------------------------------------------------------- values
    def _value(self, metric, start: date, end: date):
        if metric in MONTHLY_ONLY:
            col = MONTHLY_ONLY[metric]
            if metric == "retention_rate":
                return None
            q = read_sql(f"select avg({col}) v from metrics.metrics_monthly where month between :a and :b",
                         dict(a=start.replace(day=1), b=end))
            return q.v.iat[0]
        num, den, _ = DAILY[metric]
        q = read_sql(f"select sum({num})::float n {', sum(' + den + ')::float d' if den else ''} "
                     "from metrics.metrics_daily where date_day between :a and :b", dict(a=start, b=end))
        n = q.n.iat[0]
        return n if not den else (n / q.d.iat[0] if q.d.iat[0] else None)

    def unit(self, metric):
        return DAILY[metric][2] if metric in DAILY else ("INR" if metric == "ltv_180d_cm" else "pct")

    def compare_periods(self, metric, a: tuple[date, date], b: tuple[date, date]) -> Evidence:
        va, vb = self._value(metric, *a), self._value(metric, *b)
        ch = (vb / va - 1) if va not in (None, 0) and vb is not None else None
        u = self.unit(metric)
        pp = (vb - va) * 100 if u == "pct" and va is not None and vb is not None else None
        data = dict(metric=metric, period_a=[str(a[0]), str(a[1])], period_b=[str(b[0]), str(b[1])],
                    value_a=va, value_b=vb, pct_change=ch, pp_change=pp)
        disp = [fmt(va, u), fmt(vb, u), fmt_change(ch)] + ([f"{pp:+.2f}pp"] if pp is not None else [])
        return self._ev("compare_periods", dict(metric=metric, a=data["period_a"], b=data["period_b"]), data, disp)

    def breakdown(self, metric, dimension, a, b, top_n=4) -> Evidence | None:
        if metric not in DIM_COMPONENTS:
            return None
        num, den = DIM_COMPONENTS[metric]
        q = read_sql(f"""select dimension_value,
                sum({num}) filter (where date_day between :a0 and :a1)::float as n_a,
                sum({num}) filter (where date_day between :b0 and :b1)::float as n_b
                {f", sum({den}) filter (where date_day between :a0 and :a1)::float as d_a, sum({den}) filter (where date_day between :b0 and :b1)::float as d_b" if den else ""}
                from metrics.metrics_daily_by_dimension
                where dimension_name = :dim and date_day between least(:a0, :b0) and greatest(:a1, :b1)
                group by 1""", dict(dim=dimension, a0=a[0], a1=a[1], b0=b[0], b1=b[1])).fillna(0)
        if q.empty:
            return None
        u = self.unit(metric)
        if den:   # ratio: rate effect + mix effect per segment (sums exactly to the total change)
            w_a, w_b = q.d_a / q.d_a.sum(), q.d_b / q.d_b.sum()
            r_a = (q.n_a / q.d_a.replace(0, float("nan"))).fillna(0)
            r_b = (q.n_b / q.d_b.replace(0, float("nan"))).fillna(0)
            q["rate_effect"], q["mix_effect"] = w_b * (r_b - r_a), (w_b - w_a) * r_a
            q["contribution"] = q.rate_effect + q.mix_effect
            q["value_a"], q["value_b"] = r_a, r_b
            total = (q.n_b.sum() / q.d_b.sum()) - (q.n_a.sum() / q.d_a.sum())
        else:
            q["contribution"] = q.n_b - q.n_a
            q["value_a"], q["value_b"] = q.n_a, q.n_b
            total = q.contribution.sum()
        q["share_of_change"] = q.contribution / total if total else float("nan")
        q = q.reindex(q.contribution.abs().sort_values(ascending=False).index).head(top_n)
        rows, disp = [], []
        for r in q.itertuples():
            c = r.contribution * 100 if den and u == "pct" else r.contribution
            rows.append(dict(segment=r.dimension_value, value_a=r.value_a, value_b=r.value_b,
                             contribution=r.contribution, share_of_change=r.share_of_change))
            disp += [str(r.dimension_value), fmt(r.value_a, u), fmt(r.value_b, u),
                     (f"{c:+.2f}pp" if den and u == "pct" else fmt(c, u if u != "pct" else "INR")),
                     fmt_change(r.share_of_change).lstrip("+")]
        return self._ev("breakdown", dict(metric=metric, dimension=dimension), dict(dimension=dimension, rows=rows,
                                                                                   total_change=total), disp)

    def anomalies(self, start, end) -> Evidence:
        try:
            a = read_sql("""select metric, display, start_date, end_date, expected, actual, deviation, severity,
                                   classification from analytics.anomaly_alerts
                            where start_date <= :b and end_date >= :a and classification <> 'expected_seasonal'""",
                         dict(a=start, b=end))
            s = read_sql("""select metric, display, dimension, dimension_value, start_date, end_date, expected, actual,
                                   deviation, severity from analytics.anomaly_segment_alerts
                            where start_date <= :b and end_date >= :a""", dict(a=start, b=end))
        except Exception:
            a, s = pd.DataFrame(), pd.DataFrame()
        disp = []
        for r in pd.concat([a, s]).itertuples():
            disp += [f"{r.deviation * 100:+.1f}%", str(r.start_date), str(r.end_date)]
            if r.metric in ("payment_success_rate", "checkout_conversion", "conversion_rate"):
                disp += [f"{r.expected * 100:.1f}%", f"{r.actual * 100:.1f}%"]
        return self._ev("anomalies", dict(start=str(start), end=str(end)),
                        dict(topline=a.to_dict("records"), segments=s.to_dict("records")), disp)

    def data_quality(self, start, end) -> Evidence:
        dq = read_sql("select dimension, score from dq.dq_scorecard")
        mat = read_sql("select bool_and(is_refund_mature) m from metrics.metrics_daily where date_day between :a and :b",
                       dict(a=start, b=end)).m.iat[0]
        warn = read_sql("select check_id, description from dq.dq_checks where status <> 'pass'")
        overall = float(dq.loc[dq.dimension == "OVERALL", "score"].iat[0])
        return self._ev("data_quality", dict(start=str(start), end=str(end)),
                        dict(overall_score=overall, refund_data_mature=bool(mat), open_warnings=warn.to_dict("records")),
                        [f"{overall:.1f}", f"{len(warn)}"])

    def forecast(self) -> Evidence:
        f = read_sql("select week, p10, p50, p90, model from analytics.revenue_forecast where value_type = 'forecast'")
        tot = f[["p10", "p50", "p90"]].sum()
        return self._ev("forecast", {}, dict(weeks=len(f), model=f.model.iat[0], total_p50=tot.p50,
                                             total_p10=tot.p10, total_p90=tot.p90, first_week=str(f.week.min()),
                                             last_week=str(f.week.max())),
                        [fmt(tot.p50, "INR"), fmt(tot.p10, "INR"), fmt(tot.p90, "INR"), str(len(f))])
