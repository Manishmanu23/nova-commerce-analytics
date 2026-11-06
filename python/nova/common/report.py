"""Tiny helper for writing generated markdown reports into reports/ (committed, so reviewers see results)."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "reports"


def md_table(df: pd.DataFrame, floatfmt: str = "{:,.4g}", max_rows: int = 40) -> str:
    d = df.head(max_rows).copy()
    for c in d.columns:
        if pd.api.types.is_float_dtype(d[c]):
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else floatfmt.format(v))
    cols = [str(c) for c in d.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in d.iterrows():
        lines.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in r.values) + " |")
    return "\n".join(lines)


def write(name: str, text: str) -> Path:
    REPORTS.mkdir(exist_ok=True)
    p = REPORTS / name
    p.write_text(text.strip() + "\n")
    print(f"wrote {p.relative_to(ROOT)}")
    return p
