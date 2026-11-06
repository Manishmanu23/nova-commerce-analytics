"""
Analytics Copilot = planner -> governed tools -> (LLM or template) -> validator.

The LLM is optional. With COPILOT_PROVIDER=offline the Copilot produces deterministic template answers from
the same evidence. That keeps the product reproducible and makes it a baseline for LLM quality.
"""
from __future__ import annotations

from dataclasses import dataclass

from nova.copilot import llm, planner, prompts, validator
from nova.copilot.tools import DIMENSIONS_FOR, Tools, fmt, fmt_change


@dataclass
class Answer:
    question: str
    text: str
    evidence: list
    source: str               # llm | template | refusal
    validation_problems: list


def _sec(title, body):
    return f"### {title}\n{body.strip()}\n"


def template_answer(p: planner.Plan, ev: dict, tools: Tools) -> str:
    c = ev["compare"]
    d = c.data
    u = tools.unit(p.metric)
    name = tools.metric_info(p.metric)["display_name"]
    dirword = "rose" if (d["pct_change"] or 0) > 0 else "fell"
    lines = []
    if p.premise == "decline" and (d["pct_change"] or 0) > 0:
        lines.append(f"**Premise check:** {name} did not decline in this period. It rose {c.display[2].lstrip('+-')} [{c.id}].\n")
    if p.premise == "increase" and (d["pct_change"] or 0) < 0:
        lines.append(f"**Premise check:** {name} did not increase in this period. It fell {c.display[2].lstrip('+-')} [{c.id}].\n")
    pp = f" ({c.display[3]})" if len(c.display) > 3 else ""
    lines.append(_sec("Metric change",
                      f"{name} {dirword} from {c.display[0]} ({d['period_a'][0]} to {d['period_a'][1]}) to "
                      f"{c.display[1]} ({d['period_b'][0]} to {d['period_b'][1]}), a change of {c.display[2]}{pp} [{c.id}]."))
    contrib = []
    for b in ev["breakdowns"]:
        top = b.data["rows"][:2]
        segs = "; ".join(f"**{r['segment']}** {fmt(r['value_a'], u)} → {fmt(r['value_b'], u)} "
                         f"({fmt_change(r['share_of_change']).lstrip('+')} of the change)" for r in top)
        contrib.append(f"- by {b.data['dimension']}: {segs} [{b.id}]")
    lines.append(_sec("Major contributing dimensions", "\n".join(contrib) or
                      "- This metric is not decomposable by dimension at the governed grain."))
    sup = []
    a = ev["anomalies"]
    rel = [r for r in a.data["segments"] + a.data["topline"]
           if r["metric"].startswith(p.metric.split("_rate")[0].split("_conversion")[0][:8])]
    for r in rel[:3]:
        seg = f" in {r['dimension']} = {r['dimension_value']}" if "dimension" in r else ""
        sup.append(f"- Anomaly detector: {r['display']}{seg} deviated {r['deviation'] * 100:+.1f}% between "
                   f"{r['start_date']} and {r['end_date']} ({r['severity']}) [{a.id}].")
    if not sup:
        sup.append(f"- No non-seasonal anomaly incident overlaps this period for this metric [{a.id}].")
    lines.append(_sec("Supporting evidence", "\n".join(sup)))
    q = ev["dq"]
    lim = [f"- Data quality score {q.display[0]} / 100 with {q.display[1]} open warnings (all known and mitigated) [{q.id}]."]
    if not q.data["refund_data_mature"] and p.metric in ("refund_rate", "net_revenue", "gross_profit",
                                                         "contribution_margin", "cm_pct"):
        lim.append(f"- Refunds for part of this period are still arriving, so the figures are **provisional** "
                   f"and likely to fall as late refunds land [{q.id}].")
    lim.append("- Segment contributions show where the change is concentrated. They do not establish causes.")
    lim.append("- Attribution is last non-direct touch, which over-credits bottom-funnel channels.")
    lines.append(_sec("Uncertainty & limitations", "\n".join(lim)))
    nxt = ["- Confirm the top segment's change with source logs (release notes, gateway failure reasons, campaign calendar)."]
    if p.metric in ("payment_success_rate", "checkout_conversion_rate", "conversion_rate"):
        nxt.append("- Split by app_version and payment_method together, and check whether the failures are a new failure reason.")
    if p.metric in ("net_revenue", "contribution_margin", "cm_pct"):
        nxt.append("- Separate new vs returning customers and check the discount depth of the acquiring campaigns (CAC vs 90-day CM).")
    lines.append(_sec("Suggested next investigations", "\n".join(nxt)))
    return "\n".join(lines)


def answer(question: str, tools: Tools | None = None) -> Answer:
    tools = tools or Tools()
    p = planner.plan(question, data_end=tools.bounds.b)
    if p.intent == "refuse":
        return Answer(question, f"**I can't answer that from governed data.** {p.refusal}", [], "refusal", [])
    if p.intent == "forecast":
        f = tools.forecast()
        text = (f"### Forecast (label: FORECAST, not an actual)\nNet revenue for the next {f.display[3]} weeks is "
                f"forecast at {f.display[0]} (sum of weekly P10 {f.display[1]} to P90 {f.display[2]}) using the "
                f"`{f.data['model']}` model [{f.id}].\n\n### Uncertainty & limitations\n- Backtest error and assumptions "
                "are listed in the revenue forecast report. This is a planning input, not a target.")
        ok, probs = validator.validate(text, [f], set(tools.catalog.metric_name) | {"ets_damped_log", "mean_4w",
                                                                                     "seasonal_naive_x_growth"})
        return Answer(question, text, [f], "template", probs)
    ev = {"compare": tools.compare_periods(p.metric, p.period_a, p.period_b)}
    ev["breakdowns"] = [b for d in DIMENSIONS_FOR.get(p.metric, [])[:3]
                        if (b := tools.breakdown(p.metric, d, p.period_a, p.period_b)) is not None]
    ev["anomalies"] = tools.anomalies(p.period_b[0], p.period_b[1])
    ev["dq"] = tools.data_quality(p.period_b[0], p.period_b[1])
    evidence = [ev["compare"], *ev["breakdowns"], ev["anomalies"], ev["dq"]]
    catalog = set(tools.catalog.metric_name)
    draft = llm.complete(prompts.SYSTEM, prompts.USER.format(
        question=question, catalog=", ".join(sorted(catalog)), evidence=llm.evidence_json(evidence)))
    if draft:
        ok, probs = validator.validate(draft, evidence, catalog)
        if ok:
            return Answer(question, draft, evidence, "llm", [])
        fallback = template_answer(p, ev, tools)
        return Answer(question, fallback + "\n\n_(LLM draft rejected by the grounding validator: "
                      + "; ".join(probs[:3]) + ")_", evidence, "template", probs)
    text = template_answer(p, ev, tools)
    ok, probs = validator.validate(text, evidence, catalog)
    return Answer(question, text, evidence, "template", probs)


if __name__ == "__main__":
    import sys
    a = answer(" ".join(sys.argv[1:]) or "Why did revenue decline last month?")
    print(a.text, "\n\nsource:", a.source, "| validation problems:", a.validation_problems)
