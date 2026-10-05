"""Export the checked snapshot, SQL comparison, chart and factual findings."""

import hashlib
import json
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from nhs_ae.reporting import comparison, monthly

ROOT = Path(__file__).parent


def main():
    (ROOT / "data/demo").mkdir(exist_ok=True)
    (ROOT / "reports").mkdir(exist_ok=True)
    quality = json.loads((ROOT / "reports/quality.json").read_text())
    for file, expected in [
        ("data/nhs.duckdb", quality["database_sha256"]),
        ("data/source_manifest.json", quality["manifest_sha256"]),
    ]:
        if hashlib.sha256((ROOT / file).read_bytes()).hexdigest() != expected:
            raise ValueError(f"{file} differs from the checked build; run load.py first")
    with duckdb.connect(str(ROOT / "data/nhs.duckdb"), read_only=True) as con:
        for table, file in [("ae_provider", "providers.csv"), ("ae_national", "national.csv")]:
            order = "period_month,org_code" if table == "ae_provider" else "period_month"
            con.sql(f"SELECT * FROM {table} ORDER BY {order}").df().to_csv(
                ROOT / "data/demo" / file, index=False
            )
        c = comparison(con)
        c.to_csv(ROOT / "reports/provider_comparison.csv", index=False)
        n = monthly(con)
        all_types = monthly(con, department="all")
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.plot(n.period_month, n.within_4h_pct, color="#006cbb", label="England · Type 1")
        ax.plot(
            all_types.period_month,
            all_types.within_4h_pct,
            color="#167f86",
            label="England · all A&E types",
        )
        ax.set(
            title="A&E: time in department at most four hours",
            ylabel="Percentage of unplanned attendances",
            xlabel="Reporting month",
        )
        ax.grid(axis="y", alpha=0.2)
        ax.legend()
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(ROOT / "figures/type1_trend.png", dpi=160)
        plt.close(fig)
        annual = con.sql("""
            SELECT CASE WHEN period_month >= DATE '2025-04-01'
                THEN 'April 2025–March 2026' ELSE 'April 2024–March 2025' END AS window,
                sum(att_type1) AS type1_attendances,
                100*(1-sum(over4hr_type1)/sum(att_type1)) AS type1_within_4h_pct,
                100*(1-sum(over4hr_all)/sum(att_all)) AS all_types_within_4h_pct
            FROM ae_national GROUP BY 1 ORDER BY 1
        """).df()
        results = {
            "snapshot_end": str(n.period_month.max().date()),
            "providers_compared": len(c),
            "improved": int((c.recovery_pp > 0).sum()),
            "declined": int((c.recovery_pp < 0).sum()),
            "unchanged": int((c.recovery_pp == 0).sum()),
            "england_latest_type1_pct": float(n.within_4h_pct.iloc[-1]),
            "england_latest_type1_yoy_pp": float(n.yoy_pp.iloc[-1]),
            "england_latest_all_types_pct": float(all_types.within_4h_pct.iloc[-1]),
            "england_annual_comparison": annual.to_dict("records"),
        }
        (ROOT / "reports/findings.json").write_text(json.dumps(results, indent=2) + "\n")
        exported = [
            "data/demo/providers.csv",
            "data/demo/national.csv",
            "reports/quality.json",
            "data/source_manifest.json",
        ]
        hashes = {file: hashlib.sha256((ROOT / file).read_bytes()).hexdigest() for file in exported}
        (ROOT / "data/demo/snapshot.json").write_text(json.dumps(hashes, indent=2) + "\n")
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
