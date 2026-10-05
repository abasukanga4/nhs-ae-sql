"""Build the validated database; do not replace a good database on failure."""

import argparse
import json
from pathlib import Path

from nhs_ae.pipeline import ROOT, build_database, download_sources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data/raw")
    parser.add_argument("--database", type=Path, default=ROOT / "data/nhs.duckdb")
    parser.add_argument("--manifest", type=Path, default=ROOT / "data/source_manifest.json")
    args = parser.parse_args()
    if args.download:
        print(f"Downloaded {download_sources(args.manifest, args.raw_dir)} checked source files")
    report = build_database(args.raw_dir, args.database, args.manifest)
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports/quality.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
