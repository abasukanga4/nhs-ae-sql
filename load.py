#!/usr/bin/env python3
"""load.py — build the NHS A&E analytics database.

Thin orchestration glue only. All schema and transform logic lives in the
sql/ files; this script just wires them up in order:

    1. run sql/01_schema.sql            (create staging + clean tables)
    2. ingest every data/raw/*.csv      -> stg_ae_raw, tagging each row with
                                           its filename label (YYYY-MM) as the
                                           authoritative reporting month
    3. run sql/02_cleaning.sql          (type, split TOTAL, derive metrics)

Run:  python3 load.py
"""
from __future__ import annotations

import glob
import os
import sys

import duckdb

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT, "data", "nhs.duckdb")
RAW_DIR = os.path.join(ROOT, "data", "raw")
SQL_DIR = os.path.join(ROOT, "sql")

# The 22 source columns, in file order, mapped onto stg_ae_raw's columns
# (source_label is prepended in the INSERT, not read from the file).
STG_COLS = [
    "period_raw", "org_code", "parent_org", "org_name",
    "att_type1", "att_type2", "att_other",
    "att_booked_type1", "att_booked_type2", "att_booked_other",
    "over4hr_type1", "over4hr_type2", "over4hr_other",
    "over4hr_booked_type1", "over4hr_booked_type2", "over4hr_booked_other",
    "waited_4_12hr_dta", "waited_12hr_dta",
    "emadm_type1", "emadm_type2", "emadm_other", "emadm_other_emergency",
]


def run_sql_file(con: duckdb.DuckDBPyConnection, path: str) -> None:
    """Execute a whole .sql file (may contain multiple statements)."""
    with open(path, "r", encoding="utf-8") as fh:
        con.execute(fh.read())
    print(f"  ran {os.path.relpath(path, ROOT)}")


def ingest_csv(con: duckdb.DuckDBPyConnection, csv_path: str) -> int:
    """Load one raw CSV into stg_ae_raw, tagging rows with the YYYY-MM label.

    Read all-VARCHAR and by position (the header names are not fully uniform:
    2024-09 carries junk trailing columns). We take only the first 22 columns
    via a positional projection, so junk extra columns are ignored.
    """
    label = os.path.splitext(os.path.basename(csv_path))[0]  # e.g. '2024-04'

    # all_varchar keeps ingest permissive; header is skipped; column_names
    # forces our schema regardless of the file's (slightly variable) header.
    rel = con.read_csv(
        csv_path,
        header=True,
        all_varchar=True,
        # names supplied positionally; extra columns in the odd file are dropped.
        names=STG_COLS + [f"_junk{i}" for i in range(10)],
        null_padding=True,
        ignore_errors=True,
    )
    col_list = ", ".join(STG_COLS)
    con.execute(
        f"INSERT INTO stg_ae_raw (source_label, {col_list}) "
        f"SELECT '{label}', {col_list} FROM rel"
    )
    (n,) = con.execute("SELECT count(*) FROM rel").fetchone()
    return n


def main() -> int:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)  # deterministic rebuild

    csvs = sorted(glob.glob(os.path.join(RAW_DIR, "*.csv")))
    if not csvs:
        print("ERROR: no CSVs in data/raw/. Run: bash data/raw/download.sh",
              file=sys.stderr)
        return 1

    con = duckdb.connect(DB_PATH)
    try:
        print("1. schema")
        run_sql_file(con, os.path.join(SQL_DIR, "01_schema.sql"))

        print(f"2. ingest {len(csvs)} CSVs -> stg_ae_raw")
        total = 0
        for csv_path in csvs:
            total += ingest_csv(con, csv_path)
        (staged,) = con.execute("SELECT count(*) FROM stg_ae_raw").fetchone()
        print(f"   staged {staged} raw rows from {len(csvs)} files")

        print("3. cleaning")
        run_sql_file(con, os.path.join(SQL_DIR, "02_cleaning.sql"))

        (prov,) = con.execute("SELECT count(*) FROM ae_provider").fetchone()
        (natl,) = con.execute("SELECT count(*) FROM ae_national").fetchone()
        (months,) = con.execute(
            "SELECT count(DISTINCT period_month) FROM ae_provider"
        ).fetchone()
        print(f"   ae_provider: {prov} rows across {months} months")
        print(f"   ae_national: {natl} rows")
    finally:
        con.close()

    print(f"Built {os.path.relpath(DB_PATH, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
