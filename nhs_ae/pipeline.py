"""Fail-closed ingestion and atomic database publication for pinned NHS CSVs."""

from __future__ import annotations

import calendar
import csv
import hashlib
import io
import json
import re
import tempfile
from pathlib import Path

import duckdb
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = [
    "period_raw",
    "org_code",
    "parent_org",
    "org_name",
    "att_type1",
    "att_type2",
    "att_other",
    "att_booked_type1",
    "att_booked_type2",
    "att_booked_other",
    "over4hr_type1",
    "over4hr_type2",
    "over4hr_other",
    "over4hr_booked_type1",
    "over4hr_booked_type2",
    "over4hr_booked_other",
    "waited_4_12hr_dta",
    "waited_12hr_dta",
    "emadm_type1",
    "emadm_type2",
    "emadm_other",
    "emadm_other_emergency",
]
MEASURES = [
    "att_type1",
    "att_all",
    "over4hr_type1",
    "over4hr_all",
    "waited_4_12hr_dta",
    "waited_12hr_dta",
]


class DataQualityError(ValueError):
    """The input cannot safely support the published reporting measures."""


def parse_csv(raw: bytes, month: str) -> tuple[list[list[str]], list[str]]:
    """Reject unknown columns, lost rows, non-count values and impossible waits."""
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise DataQualityError("Invalid manifest month")
    expected = json.loads((ROOT / "data/source_columns.json").read_text())
    try:
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig")), strict=True))
    except (UnicodeError, csv.Error) as exc:
        raise DataQualityError(f"{month}: not a valid UTF-8 CSV") from exc
    if not rows or rows[0][:22] != expected:
        raise DataQualityError(f"{month}: source column order/schema changed")
    notices = []
    if len(rows[0]) > 22:
        notices.append(
            f"{month}: {len(rows[0]) - 22} trailing columns verified empty in every data row"
        )
    cleaned = []
    keys = set()
    expected_period = f"MSitAE-{calendar.month_name[int(month[5:])]}-{month[:4]}".upper()
    for line, row in enumerate(rows[1:], 2):
        if len(row) != len(rows[0]) or any(x.strip() for x in row[22:]):
            raise DataQualityError(
                f"{month}:{line}: unexpected row width or populated extra column"
            )
        values = [x.strip() for x in row[:22]]
        code = values[1].upper()
        if not code or not values[3] or code in keys:
            raise DataQualityError(f"{month}:{line}: missing organisation or duplicate code {code}")
        keys.add(code)
        values[1] = code
        if code != "TOTAL" and values[0].upper() != expected_period:
            raise DataQualityError(f"{month}:{line}: reporting period disagrees with manifest")
        for index in range(4, 22):
            value = values[index]
            if not re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)", value):
                raise DataQualityError(f"{month}:{line}: missing/invalid count in {COLUMNS[index]}")
            values[index] = str(int(value.replace(",", "")))
        for attendance, over in [(4, 10), (5, 11), (6, 12), (7, 13), (8, 14), (9, 15)]:
            if int(values[over]) > int(values[attendance]):
                raise DataQualityError(f"{month}:{line}: over-four-hour count exceeds attendances")
        cleaned.append([month, *values])
    if "TOTAL" not in keys or len(keys) < 2:
        raise DataQualityError(f"{month}: missing national total or provider rows")
    return cleaned, notices


def load_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text())
    months = [s["month"] for s in manifest["sources"]]
    expected = (
        pd.period_range(manifest["period_start"], manifest["period_end"], freq="M")
        .astype(str)
        .tolist()
    )
    if months != expected:
        raise DataQualityError("Manifest months must be ordered, unique and complete")
    return manifest


def download_sources(manifest_path: Path, raw_dir: Path) -> int:
    """Download verified pinned bytes; leave the existing raw set intact on failure."""
    manifest = load_manifest(manifest_path)
    raw_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=raw_dir) as staging, requests.Session() as session:
        session.headers["User-Agent"] = "nhs-ae-sql/2.0 (public aggregate reporting)"
        for source in manifest["sources"]:
            response = session.get(source["url"], timeout=45)
            response.raise_for_status()
            raw = response.content
            if hashlib.sha256(raw).hexdigest() != source["sha256"]:
                raise DataQualityError(
                    f"{source['month']}: source changed; review revision before updating manifest"
                )
            parse_csv(raw, source["month"])
            Path(staging, source["month"] + ".csv").write_bytes(raw)
        for source in manifest["sources"]:
            Path(staging, source["month"] + ".csv").replace(raw_dir / (source["month"] + ".csv"))
    return len(manifest["sources"])


def build_database(raw_dir: Path, db_path: Path, manifest_path: Path) -> dict:
    manifest = load_manifest(manifest_path)
    all_rows, notices = [], []
    for source in manifest["sources"]:
        raw = (raw_dir / (source["month"] + ".csv")).read_bytes()
        if hashlib.sha256(raw).hexdigest() != source["sha256"]:
            raise DataQualityError(f"{source['month']}: SHA-256 mismatch")
        rows, notes = parse_csv(raw, source["month"])
        all_rows.extend(rows)
        notices.extend(notes)
    staged = pd.DataFrame(all_rows, columns=["source_label", *COLUMNS])
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=db_path.parent) as staging:
        candidate = Path(staging, "candidate.duckdb")
        with duckdb.connect(str(candidate)) as con:
            con.execute((ROOT / "sql/01_schema.sql").read_text())
            con.register("incoming", staged)
            con.execute("INSERT INTO stg_ae_raw SELECT * FROM incoming")
            con.execute((ROOT / "sql/02_cleaning.sql").read_text())
            diffs = []
            for measure in MEASURES:
                result = con.execute(f"""
                    SELECT p.period_month, SUM(p.{measure})-n.{measure} AS difference
                    FROM ae_provider p JOIN ae_national n USING(period_month)
                    GROUP BY p.period_month,n.{measure} HAVING difference <> 0
                """).fetchall()
                diffs.extend((measure, str(month), difference) for month, difference in result)
            if diffs:
                raise DataQualityError(f"Provider/national reconciliation failed: {diffs[:4]}")
            report = {
                "status": "passed",
                "reporting_months": len(manifest["sources"]),
                "source_files": len(manifest["sources"]),
                "raw_rows": len(all_rows),
                "provider_rows": con.sql("SELECT count(*) FROM ae_provider").fetchone()[0],
                "national_rows": con.sql("SELECT count(*) FROM ae_national").fetchone()[0],
                "national_reconciliation_checks": len(MEASURES) * len(manifest["sources"]),
                "national_reconciliation_failures": len(diffs),
                "notices": notices,
                "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                "checks": [
                    "source hashes",
                    "column order",
                    "row widths",
                    "nonnegative integer counts",
                    "breaches no greater than attendances",
                    "unique organisation/month keys",
                    "source period agrees with manifest",
                    "complete month sequence",
                    "one national total per month",
                    "provider/national reconciliation",
                ],
            }
        report["database_sha256"] = hashlib.sha256(candidate.read_bytes()).hexdigest()
        candidate.replace(db_path)
    return report
