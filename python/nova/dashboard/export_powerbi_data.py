"""
Export the Power BI dataset to CSV:  python -m nova.dashboard.export_powerbi_data
Writes powerbi/data/<table>.csv (UTF-8, ISO dates, booleans as true/false) + powerbi/data/schema.json.
Why CSV? Power BI Desktop runs on Windows only. Copying a folder of CSVs into a Windows machine/VM is far
simpler than exposing a Mac's Docker Postgres to it. The PostgreSQL connection is still documented
(powerbi/power_query.m) for anyone running both on the same machine.
"""
import json

import pandas as pd

from nova.common.db import read_sql
from nova.common.report import ROOT
from nova.dashboard.pbi_spec import TABLES

OUT = ROOT / "powerbi" / "data"


def ptype(s: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(s):
        return "boolean"
    if pd.api.types.is_integer_dtype(s):
        return "int64"
    if pd.api.types.is_float_dtype(s):
        return "double"
    if pd.api.types.is_datetime64_any_dtype(s):
        return "dateTime"
    non_null = s.dropna()
    if len(non_null) and non_null.map(type).eq(bool).all():
        return "boolean"
    if len(non_null) and non_null.astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        return "dateTime"
    if len(non_null) and non_null.map(lambda v: isinstance(v, (int, float)) or hasattr(v, "as_integer_ratio")).all():
        return "double"
    return "string"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    schema = {}
    for name, sql in TABLES.items():
        df = read_sql(sql)
        cols = {}
        for c in df.columns:
            t = ptype(df[c])
            cols[c] = t
            if t == "boolean":
                df[c] = df[c].map({True: "true", False: "false"})
            elif t == "dateTime":
                df[c] = pd.to_datetime(df[c]).dt.strftime("%Y-%m-%d")
            elif t == "double":
                df[c] = pd.to_numeric(df[c])
        df.to_csv(OUT / f"{name}.csv", index=False)
        schema[name] = cols
        print(f"{name:32s} {len(df):>8,} rows  {len(cols):>3} cols")
    (OUT / "schema.json").write_text(json.dumps(schema, indent=1))


if __name__ == "__main__":
    main()
