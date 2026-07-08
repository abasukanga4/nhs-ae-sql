#!/usr/bin/env python3
"""run_analysis.py — execute the analysis SQL and render the figures.

Thin glue only: the analytical logic lives in sql/03_analysis_*.sql. This
script runs those queries against data/nhs.duckdb, pulls the result sets into
pandas, and draws three matplotlib charts into figures/.

Charts:
  1. figures/national_4hr_performance.png
       National all-types 4-hour performance, monthly + rolling 3-month
       average, with winter (Dec-Feb) shaded.
  2. figures/top10_fastest_recovery.png
       Ten acute trusts with the largest year-on-year gain in Type 1
       4-hour performance (latest-12 vs prior-12).
  3. figures/winter_vs_rest.png
       Winter-vs-rest-of-year performance, showing whether the winter floor
       is rising (recovering) or ratcheting down (structural decline).

Run:  python3 run_analysis.py   (after python3 load.py)
"""
from __future__ import annotations

import os

import duckdb
import matplotlib

matplotlib.use("Agg")  # headless: write PNGs, never open a window
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT, "data", "nhs.duckdb")
SQL_DIR = os.path.join(ROOT, "sql")
FIG_DIR = os.path.join(ROOT, "figures")

# Sentinel that separates the two result sets inside the seasonality file.
RESULT_SENTINEL = "-- >>> RESULT:"


def read_sql(name: str) -> str:
    with open(os.path.join(SQL_DIR, name), "r", encoding="utf-8") as fh:
        return fh.read()


def split_result_sets(sql_text: str) -> list[str]:
    """Split a multi-result SQL file on the RESULT sentinel into runnable parts."""
    parts, current = [], []
    for line in sql_text.splitlines():
        if line.startswith(RESULT_SENTINEL) and current:
            parts.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        parts.append("\n".join(current))
    return parts


def chart_national(con: duckdb.DuckDBPyConnection) -> str:
    """National monthly performance + rolling 3-month average, winter shaded."""
    parts = split_result_sets(read_sql("03_analysis_seasonality.sql"))
    df = con.execute(parts[0]).fetchdf()  # the monthly trace
    df["period_month"] = df["period_month"].astype("datetime64[ns]")

    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.plot(df["period_month"], df["perf_all_pct"], color="#adb5bd",
            marker="o", ms=3, lw=1, label="Monthly (all A&E types)")
    ax.plot(df["period_month"], df["perf_all_roll3_pct"], color="#1f6feb",
            lw=2.5, label="Rolling 3-month average")

    # Shade each winter (Dec-Feb) block.
    winter_label_done = False
    for season, grp in df[df["is_winter"]].groupby("winter_season"):
        ax.axvspan(grp["period_month"].min(), grp["period_month"].max(),
                   color="#cfe2ff", alpha=0.45,
                   label="Winter (Dec-Feb)" if not winter_label_done else None)
        winter_label_done = True

    ax.set_title("England A&E 4-hour performance — recovering, with a seasonal winter dip",
                 fontsize=13, fontweight="bold")
    ax.set_ylabel("% seen within 4 hours (all A&E types)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.grid(True, axis="y", ls=":", alpha=0.5)
    ax.legend(loc="lower right", framealpha=0.9)
    fig.autofmt_xdate()
    fig.tight_layout()

    out = os.path.join(FIG_DIR, "national_4hr_performance.png")
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def chart_recovery(con: duckdb.DuckDBPyConnection) -> str:
    """Top-10 fastest-recovering acute trusts (Type 1, YoY)."""
    df = con.execute(read_sql("03_analysis_recovery.sql")).fetchdf().head(10)
    df = df.iloc[::-1]  # largest gain at the top of a horizontal bar chart

    def short(name: str) -> str:
        for suffix in (" NHS FOUNDATION TRUST", " NHS TRUST",
                       " NATIONAL HEALTH SERVICE TRUST"):
            name = name.replace(suffix, "")
        return name.title()

    labels = [short(n) for n in df["org_name"]]

    fig, ax = plt.subplots(figsize=(11, 6))
    bars = ax.barh(labels, df["recovery_pp"], color="#2da44e")
    for bar, prior, latest in zip(bars, df["perf_prior_pct"], df["perf_latest_pct"]):
        ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2,
                f"{prior:.0f}%→{latest:.0f}%", va="center", fontsize=9,
                color="#333")

    ax.set_title("Fastest-recovering acute trusts — Type 1 4-hour performance\n"
                 "(latest 12 months vs prior 12 months)",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Year-on-year improvement (percentage points)")
    ax.margins(x=0.12)
    ax.grid(True, axis="x", ls=":", alpha=0.5)
    fig.tight_layout()

    out = os.path.join(FIG_DIR, "top10_fastest_recovery.png")
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def chart_winter_vs_rest(con: duckdb.DuckDBPyConnection) -> str:
    """Winter-vs-rest performance — is the winter floor rising or falling?"""
    parts = split_result_sets(read_sql("03_analysis_seasonality.sql"))
    df = con.execute(parts[1]).fetchdf()  # the winter_summary aggregate

    colors = ["#d1242f" if g.startswith("W") else "#1f6feb" for g in df["grp"]]

    fig, ax = plt.subplots(figsize=(9, 5.5))
    x = range(len(df))
    bars = ax.bar(x, df["mean_all_pct"], color=colors, width=0.6)
    # mark the worst month in each group with a tick
    ax.scatter(x, df["worst_month_all_pct"], color="black", marker="_", s=400,
               zorder=3, label="Worst month in group")
    for i, v in zip(x, df["mean_all_pct"]):
        ax.text(i, v + 0.15, f"{v:.1f}%", ha="center", fontsize=10,
                fontweight="bold")

    ax.set_xticks(list(x))
    ax.set_xticklabels(df["grp"])
    ax.set_ylim(68, 76)
    ax.set_ylabel("Mean % seen within 4 hours (all A&E types)")
    ax.set_title("Winter vs rest-of-year — the winter floor is rising, not ratcheting down",
                 fontsize=12, fontweight="bold")
    ax.grid(True, axis="y", ls=":", alpha=0.5)
    ax.legend(loc="upper left")
    fig.tight_layout()

    out = os.path.join(FIG_DIR, "winter_vs_rest.png")
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def main() -> int:
    os.makedirs(FIG_DIR, exist_ok=True)
    con = duckdb.connect(DB_PATH, read_only=True)
    try:
        for fn in (chart_national, chart_recovery, chart_winter_vs_rest):
            out = fn(con)
            print(f"  wrote {os.path.relpath(out, ROOT)}")
    finally:
        con.close()
    print("Figures rendered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
