"""test_load.py — data-quality tests for the built NHS A&E database.

These run against data/nhs.duckdb, so build it first:

    bash data/raw/download.sh
    python3 load.py
    pytest

Each test asserts a contract the cleaning SQL must uphold. They are the
guardrail that lets the MEMO quote numbers with confidence.
"""
from __future__ import annotations

import os

import duckdb
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "nhs.duckdb")

# The 24 reporting months we expect, Apr 2024 -> Mar 2026 inclusive.
EXPECTED_MONTHS = [
    f"{y}-{m:02d}-01"
    for y in (2024, 2025, 2026)
    for m in range(1, 13)
    if not (y == 2024 and m < 4) and not (y == 2026 and m > 3)
]


@pytest.fixture(scope="module")
def con():
    if not os.path.exists(DB_PATH):
        pytest.fail(
            "data/nhs.duckdb not found. Build it first:\n"
            "  bash data/raw/download.sh && python3 load.py"
        )
    connection = duckdb.connect(DB_PATH, read_only=True)
    yield connection
    connection.close()


def test_clean_tables_nonempty(con):
    """(1) Every clean table has rows."""
    for table in ("ae_provider", "ae_national"):
        (n,) = con.execute(f"SELECT count(*) FROM {table}").fetchone()
        assert n > 0, f"{table} is empty"


def test_no_duplicate_primary_key(con):
    """(2) (period_month, org_code) is unique in the provider table."""
    (dupes,) = con.execute(
        """
        SELECT count(*) FROM (
            SELECT period_month, org_code
            FROM ae_provider
            GROUP BY period_month, org_code
            HAVING count(*) > 1
        )
        """
    ).fetchone()
    assert dupes == 0, f"{dupes} duplicate (period_month, org_code) keys"


def test_performance_metric_in_unit_interval(con):
    """(3) Every non-null performance value lies in [0, 1]."""
    for col in ("perf_all", "perf_type1"):
        row = con.execute(
            f"""
            SELECT count(*) FROM ae_provider
            WHERE {col} IS NOT NULL AND ({col} < 0 OR {col} > 1)
            """
        ).fetchone()
        assert row[0] == 0, f"{col} has {row[0]} values outside [0, 1]"
    # and the national series too
    for col in ("perf_all", "perf_type1"):
        row = con.execute(
            f"SELECT min({col}), max({col}) FROM ae_national"
        ).fetchone()
        assert 0.0 <= row[0] <= row[1] <= 1.0, f"national {col} out of range: {row}"


def test_all_expected_months_present(con):
    """(4) All 24 expected months appear in both clean tables."""
    for table in ("ae_provider", "ae_national"):
        months = {
            str(r[0])
            for r in con.execute(
                f"SELECT DISTINCT period_month FROM {table}"
            ).fetchall()
        }
        missing = set(EXPECTED_MONTHS) - months
        extra = months - set(EXPECTED_MONTHS)
        assert not missing, f"{table} missing months: {sorted(missing)}"
        assert not extra, f"{table} has unexpected months: {sorted(extra)}"
        assert len(months) == 24, f"{table} has {len(months)} months, expected 24"


def test_national_total_separated(con):
    """(5) The TOTAL row is in ae_national, never in ae_provider.

    ae_national should hold exactly one row per month (the England TOTAL),
    and no 'TOTAL' org code should leak into the provider table under any
    casing/whitespace variant.
    """
    (leaked,) = con.execute(
        "SELECT count(*) FROM ae_provider WHERE upper(trim(org_code)) = 'TOTAL'"
    ).fetchone()
    assert leaked == 0, f"{leaked} TOTAL rows leaked into ae_provider"

    (natl,) = con.execute("SELECT count(*) FROM ae_national").fetchone()
    assert natl == 24, f"ae_national should have 24 rows, has {natl}"

    # Sanity: national all-types attendances must exceed any single provider's
    # in the same month (the total is genuinely an aggregate, not a stray row).
    (bad,) = con.execute(
        """
        SELECT count(*) FROM ae_national n
        WHERE n.att_all <= (
            SELECT max(p.att_all) FROM ae_provider p
            WHERE p.period_month = n.period_month
        )
        """
    ).fetchone()
    assert bad == 0, "a national TOTAL is not larger than its providers"
