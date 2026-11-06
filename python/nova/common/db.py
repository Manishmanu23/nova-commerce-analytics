"""Single place for database connectivity. Credentials come from environment variables (.env), never code."""
import os
from contextlib import contextmanager

import pandas as pd
import psycopg
from sqlalchemy import create_engine, text


def _cfg():
    return dict(host=os.getenv("PGHOST", "localhost"), port=int(os.getenv("PGPORT", "5432")),
                user=os.getenv("PGUSER", "nova"), password=os.getenv("PGPASSWORD", "nova"),
                dbname=os.getenv("PGDATABASE", "nova"))


def connect(**kw):
    return psycopg.connect(**_cfg(), **kw)


_engine = None


def engine():
    global _engine
    if _engine is None:
        c = _cfg()
        _engine = create_engine(
            f"postgresql+psycopg://{c['user']}:{c['password']}@{c['host']}:{c['port']}/{c['dbname']}")
    return _engine


def read_sql(sql: str, params: dict | None = None) -> pd.DataFrame:
    with engine().connect() as con:
        return pd.read_sql(text(sql), con, params=params or {})


def write_df(df: pd.DataFrame, table: str, schema: str = "analytics", if_exists: str = "replace"):
    """Create/replace the table from the DataFrame schema, then bulk-load with COPY (fast, no param limits)."""
    import io
    with engine().begin() as con:
        con.execute(text(f"create schema if not exists {schema}"))
    df.head(0).to_sql(table, engine(), schema=schema, if_exists=if_exists, index=False)
    if df.empty:
        return
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False)
    cols = ", ".join('"' + str(c).replace('"', '""') + '"' for c in df.columns)
    with connect() as conn, conn.cursor() as cur:
        with cur.copy(f'copy {schema}."{table}" ({cols}) from stdin with (format csv)') as cp:
            cp.write(buf.getvalue())
        conn.commit()


@contextmanager
def cursor():
    with connect(autocommit=True) as conn:
        with conn.cursor() as cur:
            yield cur
