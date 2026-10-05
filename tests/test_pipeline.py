import csv
import hashlib
import io
import json

import duckdb
import pytest

from nhs_ae.pipeline import ROOT, DataQualityError, build_database, parse_csv


def sample_csv(month="2024-04", attendance="100", breaches="20", extra=False):
    headers = json.loads((ROOT / "data/source_columns.json").read_text())
    period = "MSitAE-APRIL-2024" if month == "2024-04" else "MSitAE-MAY-2024"
    provider = [
        period,
        "ABC",
        "Region",
        "Example Trust",
        attendance,
        "0",
        "0",
        "0",
        "0",
        "0",
        breaches,
        *(["0"] * 11),
    ]
    total = ["Total"] * 4 + provider[4:]
    if extra:
        headers += ["unused"]
        provider += [""]
        total += [""]
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerows([headers, provider, total])
    return stream.getvalue().encode()


def fixture_files(tmp_path, raw=None):
    raw = raw or sample_csv()
    (tmp_path / "2024-04.csv").write_bytes(raw)
    manifest = {
        "period_start": "2024-04",
        "period_end": "2024-04",
        "sources": [{"month": "2024-04", "sha256": hashlib.sha256(raw).hexdigest()}],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


@pytest.mark.parametrize("value", ["", "NaN", "*", "-1", "1.5", "1,2", "unknown"])
def test_unknown_counts_do_not_turn_into_zero(value):
    with pytest.raises(DataQualityError, match="invalid count"):
        parse_csv(sample_csv(attendance=value), "2024-04")


def test_thousands_and_empty_extra_columns():
    rows, notes = parse_csv(sample_csv(attendance="1,000", extra=True), "2024-04")
    assert rows[0][5] == "1000"
    assert len(notes) == 1


def test_breaches_cannot_exceed_attendances():
    with pytest.raises(DataQualityError, match="exceeds"):
        parse_csv(sample_csv(attendance="10", breaches="20"), "2024-04")


def test_duplicate_org_fails():
    text = sample_csv().decode().splitlines()
    with pytest.raises(DataQualityError, match="duplicate"):
        parse_csv(("\n".join(text + [text[1]]) + "\n").encode(), "2024-04")


def test_header_order_checked():
    raw = sample_csv().replace(b"Org Code,Parent Org", b"Parent Org,Org Code")
    with pytest.raises(DataQualityError, match="schema"):
        parse_csv(raw, "2024-04")


def test_source_month_checked():
    with pytest.raises(DataQualityError, match="period disagrees"):
        parse_csv(sample_csv(), "2024-05")


def test_populated_extra_column_fails():
    raw = sample_csv(extra=True).replace(b"0,\r\n", b"0,hidden\r\n", 1)
    with pytest.raises(DataQualityError, match="extra column"):
        parse_csv(raw, "2024-04")


def test_build_and_zero_denominator(tmp_path):
    manifest = fixture_files(tmp_path, sample_csv(attendance="0", breaches="0"))
    db = tmp_path / "test.duckdb"
    report = build_database(tmp_path, db, manifest)
    assert report["national_reconciliation_checks"] == 6
    with duckdb.connect(str(db), read_only=True) as con:
        assert con.sql("SELECT perf_type1 FROM ae_provider").fetchone()[0] is None


def test_failed_build_preserves_previous_database(tmp_path):
    manifest = fixture_files(tmp_path)
    db = tmp_path / "test.duckdb"
    build_database(tmp_path, db, manifest)
    before = db.read_bytes()
    (tmp_path / "2024-04.csv").write_bytes(b"broken")
    with pytest.raises(DataQualityError, match="SHA-256"):
        build_database(tmp_path, db, manifest)
    assert db.read_bytes() == before


def test_national_mismatch_fails_without_replacing_database(tmp_path):
    raw = (
        sample_csv()
        .decode()
        .replace("Total,Total,Total,Total,100", "Total,Total,Total,Total,101")
        .encode()
    )
    manifest = fixture_files(tmp_path, raw)
    db = tmp_path / "existing.duckdb"
    db.write_bytes(b"existing database")
    with pytest.raises(DataQualityError, match="reconciliation"):
        build_database(tmp_path, db, manifest)
    assert db.read_bytes() == b"existing database"


def test_missing_manifest_month_fails(tmp_path):
    manifest = fixture_files(tmp_path)
    s = json.loads(manifest.read_text())
    s["period_end"] = "2024-05"
    manifest.write_text(json.dumps(s))
    with pytest.raises(DataQualityError, match="complete"):
        build_database(tmp_path, tmp_path / "test.duckdb", manifest)


def test_integer_overflow_fails_without_replacing_database(tmp_path):
    manifest = fixture_files(tmp_path, sample_csv(attendance=str(2**63)))
    db = tmp_path / "existing.duckdb"
    db.write_bytes(b"previous checked database")
    with pytest.raises(duckdb.ConversionException):
        build_database(tmp_path, db, manifest)
    assert db.read_bytes() == b"previous checked database"
