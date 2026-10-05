"""Check the portable BI artifact against the reporting snapshot, not a mock."""

import csv
import io
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "bi/Hospital Performance Explorer.twbx"


@pytest.fixture
def package():
    with zipfile.ZipFile(PACKAGE) as archive:
        yield archive


def test_packaged_data_is_exact_reporting_snapshot(package):
    assert set(package.namelist()) == {
        "Hospital Performance Explorer.twb",
        "Data/providers.csv",
        "Data/Extracts/providers.hyper",
    }
    assert package.read("Data/providers.csv") == (ROOT / "data/demo/providers.csv").read_bytes()
    assert package.read("Data/Extracts/providers.hyper").startswith(b"Hyper")


def test_portable_connections_and_renderable_sheets(package):
    raw = package.read("Hospital Performance Explorer.twb")
    workbook = ET.fromstring(raw)
    for forbidden in [b"/Users/", b"localhost", b'password="secret', b"C:\\\\"]:
        assert forbidden not in raw
    sheets = {s.attrib["name"] for s in workbook.findall("./worksheets/worksheet")}
    assert len(sheets) == 3
    windows = {
        w.attrib["name"]
        for w in workbook.findall("./windows/window")
        if w.attrib["class"] == "worksheet" and w.find("viewpoint") is not None
    }
    assert sheets == windows
    extract = workbook.find("./datasources/datasource[@name='provider_data']/extract")
    assert extract.attrib["enabled"] == "true"
    assert extract.find("connection").attrib["dbname"] in package.namelist()
    assert {
        z.attrib["name"]
        for z in workbook.findall("./dashboards/dashboard/zones/zone")
        if "name" in z.attrib
    } == sheets


def test_parameter_values_and_weighted_calculation(package):
    workbook = ET.fromstring(package.read("Hospital Performance Explorer.twb"))
    parameters = workbook.find("./datasources/datasource[@name='Parameters']")
    actual = {c.attrib["name"]: c for c in parameters.findall("column")}
    assert set(actual) == {"[Provider]", "[Department]", "[Window]"}
    for column in actual.values():
        choices = {m.attrib["value"] for m in column.findall("members/member")}
        assert column.attrib["value"] in choices
    assert actual["[Window]"].attrib["value"] == '"Latest 12 months"'
    ds = workbook.find("./datasources/datasource[@name='provider_data']")
    rate = ds.find("column[@name='[Within four hours]']/calculation").attrib["formula"]
    assert "SUM([Selected over four hours]) / SUM([Selected attendances])" in rate
    assert "AVG(" not in rate
    assert "SUM([Selected attendances]) > 0" in rate
    for sheet in workbook.findall("./worksheets/worksheet"):
        assert sheet.find(".//filter/groupfilter").attrib["member"] == "true"


@pytest.mark.parametrize(
    "department,attendances,rate",
    [
        ("type1", 16744864, 0.60556472719456),
        ("all", 26969593, 0.7436602398857113),
    ],
)
def test_default_window_matches_published_totals(package, department, attendances, rate):
    rows = csv.DictReader(io.StringIO(package.read("Data/providers.csv").decode()))
    rows = [r for r in rows if "2025-04-01" <= r["period_month"] <= "2026-03-01"]
    att = sum(int(r[f"att_{department}"]) for r in rows)
    over = sum(int(r[f"over4hr_{department}"]) for r in rows)
    assert att == attendances
    assert 1 - over / att == pytest.approx(rate, abs=1e-6)


def test_hyper_extract_matches_every_csv_value(package, tmp_path):
    hyper = pytest.importorskip("tableauhyperapi")
    extract = tmp_path / "providers.hyper"
    extract.write_bytes(package.read("Data/Extracts/providers.hyper"))
    rows = list(csv.DictReader(io.StringIO(package.read("Data/providers.csv").decode())))
    expected = []
    for row in rows:
        expected.append(
            tuple(
                None
                if value == ""
                else date.fromisoformat(value)
                if key == "period_month"
                else value
                if key in {"org_code", "org_name", "region"}
                else float(value)
                if key.startswith("perf_")
                else int(value)
                for key, value in row.items()
            )
        )
    with (
        hyper.HyperProcess(
            hyper.Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU, parameters={"log_config": ""}
        ) as process,
        hyper.Connection(process.endpoint, extract) as conn,
    ):
        actual = [
            (date.fromisoformat(str(row[0])), *row[1:])
            for row in conn.execute_list_query(
                'SELECT * FROM "Extract"."Extract" ORDER BY "period_month", "org_code"'
            )
        ]
    assert actual == sorted(expected, key=lambda row: (row[0], row[1]))
    assert len(actual) == 4758
