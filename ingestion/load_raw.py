"""
Idempotent loader: data/landing/<batch_date>/<table>.csv  ->  raw.<table>

Design decisions (defend these in interviews):
  * RAW IS TEXT. Casting happens in dbt staging, where failures are visible & testable.
    A single malformed date must not stop the whole load.
  * APPEND-ONLY + METADATA. Every row gets _batch_id, _source_file, _loaded_at so we can
    dedupe, replay, and answer "when did we learn this?" (late-arriving data).
  * IDEMPOTENT. A file is identified by its SHA-256. Re-running the job never double-loads.
  * CONTRACT CHECK. Missing required columns -> file rejected (not silently loaded).
    New unexpected columns -> schema drift logged + column added (non-breaking change).
  * ATOMIC. Each file loads in one transaction: all rows or none.

Usage:  python ingestion/load_raw.py --landing data/landing [--full-refresh]
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from nova.common.db import connect  # noqa: E402

log = logging.getLogger("ingest")
CONTRACTS = yaml.safe_load((Path(__file__).parent / "schemas" / "contracts.yml").read_text())

AUDIT_DDL = """
create schema if not exists raw;
create table if not exists raw._ingestion_audit (
    audit_id      bigserial primary key,
    batch_id      text not null,
    table_name    text not null,
    source_file   text not null,
    file_hash     text not null,
    row_count     bigint,
    status        text not null,          -- success | rejected | failed
    message       text,
    started_at    timestamptz not null default now(),
    finished_at   timestamptz
);
create unique index if not exists ux_audit_hash_success
    on raw._ingestion_audit (file_hash) where status = 'success';
"""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def q(ident: str) -> str:
    return '"' + ident.replace('"', '""') + '"'


def load_file(conn, batch_id: str, path: Path) -> str:
    table = path.stem
    fhash = sha256(path)
    with conn.cursor() as cur:
        cur.execute("select 1 from raw._ingestion_audit where file_hash=%s and status='success'", (fhash,))
        if cur.fetchone():
            log.info("skip  %-24s %s (already loaded)", table, batch_id)
            return "skipped"
        header = path.open().readline().strip().split(",")
        contract = CONTRACTS.get(table)
        if contract is None:
            msg = f"no contract for table {table}"
        else:
            missing = [c for c in contract["required"] if c not in header]
            msg = f"missing required columns {missing}" if missing else None
        if msg:
            cur.execute("insert into raw._ingestion_audit(batch_id,table_name,source_file,file_hash,status,message,"
                        "finished_at) values (%s,%s,%s,%s,'rejected',%s,now())",
                        (batch_id, table, str(path), fhash, msg))
            conn.commit()
            log.error("REJECT %s: %s", path, msg)
            return "rejected"
        t0 = time.time()
        cols_sql = ", ".join(f"{q(c)} text" for c in header)
        cur.execute(f"create table if not exists raw.{q(table)} ({cols_sql}, _batch_id text, "
                    f"_source_file text, _loaded_at timestamptz default now())")
        cur.execute("select column_name from information_schema.columns where table_schema='raw' and table_name=%s",
                    (table,))
        existing = {r[0] for r in cur.fetchall()}
        drift = [c for c in header if c not in existing]
        for c in drift:                                   # non-breaking schema evolution
            cur.execute(f"alter table raw.{q(table)} add column {q(c)} text")
        cur.execute(f"create temp table _stage ({cols_sql}) on commit drop")
        with cur.copy(f"copy _stage ({', '.join(q(c) for c in header)}) from stdin with (format csv, header true)") as cp:
            with open(path, "rb") as f:
                while chunk := f.read(1 << 20):
                    cp.write(chunk)
        collist = ", ".join(q(c) for c in header)
        cur.execute(f"insert into raw.{q(table)} ({collist}, _batch_id, _source_file) "
                    f"select {collist}, %s, %s from _stage", (batch_id, path.name))
        n = cur.rowcount
        cur.execute("insert into raw._ingestion_audit(batch_id,table_name,source_file,file_hash,row_count,status,"
                    "message,finished_at) values (%s,%s,%s,%s,%s,'success',%s,now())",
                    (batch_id, table, str(path), fhash, n, f"schema drift: {drift}" if drift and existing else None))
    conn.commit()
    log.info("load  %-24s %s %10s rows %6.1fs", table, batch_id, f"{n:,}", time.time() - t0)
    return "loaded"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--landing", default="data/landing")
    ap.add_argument("--full-refresh", action="store_true", help="drop and rebuild the raw schema")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    landing = Path(a.landing)
    batches = sorted(p for p in landing.iterdir() if p.is_dir())
    if not batches:
        sys.exit(f"no batches found in {landing}")
    with connect() as conn:
        with conn.cursor() as cur:
            if a.full_refresh:
                cur.execute("drop schema if exists raw cascade")
            cur.execute(AUDIT_DDL)
        conn.commit()
        results = {}
        for b in batches:
            for f in sorted(b.glob("*.csv")):
                try:
                    results[(b.name, f.stem)] = load_file(conn, b.name, f)
                except Exception as e:  # keep going; failure is audited
                    conn.rollback()
                    with conn.cursor() as cur:
                        cur.execute("insert into raw._ingestion_audit(batch_id,table_name,source_file,file_hash,"
                                    "status,message,finished_at) values (%s,%s,%s,%s,'failed',%s,now())",
                                    (b.name, f.stem, str(f), sha256(f), str(e)[:500]))
                    conn.commit()
                    log.exception("FAILED %s", f)
                    results[(b.name, f.stem)] = "failed"
    bad = [k for k, v in results.items() if v in ("failed", "rejected")]
    log.info("summary: %s", {s: list(results.values()).count(s) for s in set(results.values())})
    if bad:
        sys.exit(f"ingestion finished with problems: {bad}")


if __name__ == "__main__":
    main()
