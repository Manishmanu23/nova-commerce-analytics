"""
Persist dbt test outcomes into dq.dbt_test_results so the DQ scorecard and Power BI can trend them.
Reads dbt/nova_dbt/target/run_results.json + manifest.json after `dbt build`.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from nova.common.db import write_df

TARGET = Path(__file__).resolve().parents[3] / "dbt" / "nova_dbt" / "target"


def main():
    rr = json.loads((TARGET / "run_results.json").read_text())
    manifest = json.loads((TARGET / "manifest.json").read_text())
    nodes = manifest["nodes"]
    rows = []
    run_at = rr["metadata"].get("generated_at", datetime.now(timezone.utc).isoformat())
    for r in rr["results"]:
        uid = r["unique_id"]
        if not uid.startswith("test."):
            continue
        n = nodes.get(uid, {})
        meta = n.get("test_metadata") or {}
        refs = n.get("depends_on", {}).get("nodes", [])
        model = next((x.split(".")[-1] for x in refs if x.startswith(("model.", "source."))), None)
        rows.append(dict(run_at=run_at, test_id=uid, test_name=n.get("name"),
                         test_type=meta.get("name", "singular"), model=model, column_name=n.get("column_name"),
                         severity=(n.get("config") or {}).get("severity", "ERROR").upper(),
                         status=r["status"], failures=r.get("failures") or 0,
                         execution_s=round(r.get("execution_time", 0), 3)))
    df = pd.DataFrame(rows)
    write_df(df, "dbt_test_results", schema="dq", if_exists="append")
    print(df.status.value_counts().to_dict())


if __name__ == "__main__":
    main()
