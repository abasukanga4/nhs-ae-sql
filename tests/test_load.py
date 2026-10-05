"""The shipped demonstration uses the same values as the checked source build."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from nhs_ae import reporting

ROOT = Path(__file__).resolve().parents[1]


def test_report_binds_to_source_manifest():
    quality = json.loads((ROOT / "reports/quality.json").read_text())
    digest = hashlib.sha256((ROOT / "data/source_manifest.json").read_bytes()).hexdigest()
    assert quality["manifest_sha256"] == digest
    assert quality["national_reconciliation_checks"] == 144
    assert quality["national_reconciliation_failures"] == 0


def test_dashboard_rejects_changed_snapshot(tmp_path, monkeypatch):
    for directory in ["data/demo", "reports"]:
        shutil.copytree(ROOT / directory, tmp_path / directory)
    shutil.copy(ROOT / "data/source_manifest.json", tmp_path / "data/source_manifest.json")
    target = tmp_path / "data/demo/providers.csv"
    target.write_text(target.read_text() + "\n")
    monkeypatch.setattr(reporting, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="Snapshot mismatch"):
        reporting.connect_snapshot()
