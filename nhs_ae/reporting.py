"""SQL-based analysis shared by the dashboard, exports and tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def connect_snapshot():
    """Use checked-in public demo data, never silently replace it with a local DB."""
    hashes = json.loads((ROOT / "data/demo/snapshot.json").read_text())
    for file in [
        "data/demo/providers.csv",
        "data/demo/national.csv",
        "reports/quality.json",
        "data/source_manifest.json",
    ]:
        if hashlib.sha256((ROOT / file).read_bytes()).hexdigest() != hashes[file]:
            raise ValueError(f"Snapshot mismatch: {file}; rebuild before displaying results")
    con = duckdb.connect(":memory:")
    for table, file in [("ae_provider", "providers.csv"), ("ae_national", "national.csv")]:
        frame = pd.read_csv(ROOT / "data/demo" / file, parse_dates=["period_month"])
        con.register("source", frame)
        con.execute(f"CREATE TABLE {table} AS SELECT * FROM source")
        con.unregister("source")
    return con


def providers(con):
    return con.sql("""SELECT org_code, arg_max(org_name,period_month) AS org_name,
        arg_max(region,period_month) AS region FROM ae_provider
        GROUP BY org_code ORDER BY org_name""").df()


def monthly(con, org_code=None, department="type1"):
    if department not in {"type1", "all"}:
        raise ValueError("Unknown department group")
    table = "ae_provider" if org_code else "ae_national"
    where = "WHERE org_code = ?" if org_code else ""
    query = f"""
        WITH base AS (
            SELECT period_month, att_{department} AS attendances,
                over4hr_{department} AS over_4h, waited_12hr_dta AS dta_12h,
                100.0*(1-over4hr_{department}/NULLIF(att_{department},0)) AS within_4h_pct
            FROM {table} {where}
        ), smooth AS (
            SELECT *, CASE WHEN count(*) OVER w = 3 THEN
                100.0*(1-SUM(over_4h) OVER w/NULLIF(SUM(attendances) OVER w,0))
                END AS rolling_3m_pct
            FROM base WINDOW w AS (ORDER BY period_month
                RANGE BETWEEN INTERVAL 2 MONTH PRECEDING AND CURRENT ROW)
        )
        SELECT a.*, a.within_4h_pct-b.within_4h_pct AS yoy_pp,
            a.attendances-b.attendances AS yoy_attendances
        FROM smooth a LEFT JOIN base b
          ON b.period_month = a.period_month - INTERVAL 1 YEAR
        ORDER BY a.period_month
    """
    return con.execute(query, [org_code] if org_code else []).df()


def comparison(con, min_annual_attendances=60000):
    return con.execute(
        (ROOT / "sql/03_analysis_recovery.sql").read_text(), [min_annual_attendances]
    ).df()


def period_summary(frame):
    volume = int(frame.attendances.sum())
    return {
        "attendances": volume,
        "over_4h": int(frame.over_4h.sum()),
        "performance": 100 * (1 - frame.over_4h.sum() / volume) if volume else None,
    }
