"""Hospital performance explorer — public aggregate NHS England data."""

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from nhs_ae.reporting import comparison, connect_snapshot, monthly, providers

ROOT = Path(__file__).parent
st.set_page_config(page_title="Hospital Performance | A&E", page_icon="↗", layout="wide")
st.markdown(
    """<style>
.block-container{padding-top:4rem;max-width:1360px}
h1{letter-spacing:-.045em} [data-testid="stMetric"]{background:#f0f5fa;padding:16px;border-radius:10px;border:1px solid #dce6ef}
[data-testid="stMetricLabel"]{color:#425a70}
</style>""",
    unsafe_allow_html=True,
)


@st.cache_data
def load_data():
    with connect_snapshot() as con:
        roster = providers(con)
    return (
        roster,
        json.loads((ROOT / "data/source_manifest.json").read_text()),
        json.loads((ROOT / "reports/quality.json").read_text()),
    )


@st.cache_data
def trend(code, group):
    with connect_snapshot() as con:
        return monthly(con, code, group)


@st.cache_data
def peers(minimum):
    with connect_snapshot() as con:
        return comparison(con, minimum)


def percent(value):
    return "No activity" if pd.isna(value) else f"{value:.1f}%"


def style_chart(fig, height=370):
    fig.update_layout(
        height=height,
        margin={"l": 5, "r": 5, "t": 24, "b": 5},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#263b50"},
        legend={"orientation": "h", "y": 1.12},
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#e2e8ef")
    return fig


roster, manifest, quality = load_data()
labels = {
    "England": None,
    **{f"{r.org_name.title()} ({r.org_code})": r.org_code for r in roster.itertuples()},
}
st.sidebar.markdown("### Explore the reporting snapshot")
selected = st.sidebar.selectbox("Organisation", list(labels))
code = labels[selected]
department_label = st.sidebar.radio("Department group", ["Type 1 · major A&E", "All A&E types"])
group = "type1" if department_label.startswith("Type 1") else "all"
months_to_show = st.sidebar.select_slider("Months displayed", [6, 12, 24], value=24)
st.sidebar.caption(
    "England aggregates. Trust reporting units may contain multiple hospital sites. This is a historical portfolio study, not a live operational service."
)
st.sidebar.markdown(
    "[Source and definitions](https://www.england.nhs.uk/statistics/statistical-work-areas/ae-waiting-times-and-activity/)"
)

st.caption("HOSPITAL PERFORMANCE / PUBLIC DATA STUDY")
st.title("A clearer view of A&E pressure")
st.markdown(
    "Explore demand, time in department and year-on-year changes — with the denominators and reporting checks visible."
)
st.caption(
    f"Snapshot: April 2024 – March 2026 · {quality['provider_rows']:,} provider-months · source files checked {manifest['retrieved_at'][:10]}"
)

series = trend(code, group)
if series.empty:
    st.info("No data for this organisation. Choose another reporting unit.")
    st.stop()
last = series.iloc[-1]
chart_data = series.tail(months_to_show)
cols = st.columns(4)
cols[0].metric("Latest attendances", f"{last.attendances:,.0f}")
cols[1].metric("Within four hours", percent(last.within_4h_pct))
cols[2].metric(
    "Year-on-year change",
    "Not available" if pd.isna(last.yoy_pp) else f"{last.yoy_pp:+.1f} pp",
)
cols[3].metric("Over four hours", f"{last.over_4h:,.0f}")
st.caption(
    f"{selected} · {department_label} · latest month {last.period_month:%B %Y}. Four hours means arrival to admission, transfer or discharge, not time to first assessment. Booked appointments excluded."
)

t_overview, t_peers, t_quality = st.tabs(
    ["Performance & briefing", "Compare providers", "Data checks & methods"]
)
with t_overview:
    left, right = st.columns([2, 1])
    with left:
        st.subheader("Time in department")
        display = chart_data[["period_month", "within_4h_pct", "rolling_3m_pct"]].rename(
            columns={"within_4h_pct": "Monthly", "rolling_3m_pct": "Three-month weighted"}
        )
        if code:
            national = trend(None, group)[["period_month", "within_4h_pct"]].rename(
                columns={"within_4h_pct": "England"}
            )
            display = display.merge(national, on="period_month", how="left")
        long = display.melt("period_month", var_name="Series", value_name="Within four hours (%)")
        fig = px.line(
            long,
            x="period_month",
            y="Within four hours (%)",
            color="Series",
            markers=True,
            color_discrete_sequence=["#006cbb", "#14a38b", "#8498ad"],
            labels={"period_month": ""},
        )
        st.plotly_chart(style_chart(fig), use_container_width=True)
        st.caption(
            "Three-month rate = 1 − summed breaches / summed attendances. The first two months are left blank. England is context, not a case-mix-adjusted benchmark."
        )
    with right:
        st.subheader("What to investigate")
        if pd.notna(last.yoy_pp):
            direction = "higher" if last.yoy_pp >= 0 else "lower"
            st.markdown(
                f"**{abs(last.yoy_pp):.1f} percentage points {direction}** than the same month a year earlier."
            )
        st.write(
            "Check reporting changes, service configuration and demand before attributing the movement to a local intervention."
        )
        st.write(
            "Bring the trend and exceptions to a discussion with operational colleagues. This dataset cannot explain staffing, bed availability or individual patient outcomes."
        )
        st.caption(
            "Two winters are too few to distinguish structural change from seasonality reliably."
        )
    st.subheader("Activity and waits")
    activity = px.bar(
        chart_data,
        x="period_month",
        y="attendances",
        color_discrete_sequence=["#006cbb"],
        labels={"period_month": "", "attendances": "Unplanned attendances"},
    )
    st.plotly_chart(style_chart(activity, 250), use_container_width=True)
    st.caption(
        "Attendance counts count visits, not unique patients. Twelve-hour decision-to-admit waits use a different clock and are not the same as twelve hours since arrival."
    )
    with st.expander("View monthly data and export a briefing"):
        st.dataframe(chart_data, hide_index=True, width="stretch")
        st.download_button(
            "Download selected monthly data",
            chart_data.to_csv(index=False),
            "ae-monthly-report.csv",
            "text/csv",
        )
        note = f"""# A&E reporting brief\n\nOrganisation: {selected}\nDepartment group: {department_label}\nSnapshot: April 2024–March 2026; historical public aggregate data.\n\nLatest month: {last.period_month:%B %Y}\nAttendances: {last.attendances:,.0f}\nWithin four hours: {percent(last.within_4h_pct)}\nOver four hours: {last.over_4h:,.0f}\n\nInterpretation: descriptive signal for investigation, not evidence of causation, clinical quality or individual patient outcomes.\nCheck case mix, reporting changes and organisational boundaries with local colleagues.\nSource: NHS England A&E Attendances and Emergency Admissions.\n"""
        st.download_button(
            "Download briefing notes", note, "ae-reporting-brief.md", "text/markdown"
        )
with t_peers:
    st.subheader("Same-provider change across two complete years")
    st.caption(
        "Type 1 only · April 2025–March 2026 versus April 2024–March 2025 · these fixed windows are independent of the chart month selector."
    )
    minimum = st.number_input(
        "Minimum Type 1 attendances in each year",
        min_value=0,
        max_value=500000,
        value=60000,
        step=10000,
    )
    table = peers(minimum)
    regions = ["All regions", *sorted(table.region.dropna().unique())]
    region = st.selectbox("Region", regions)
    if region != "All regions":
        table = table[table.region == region]
    ordering = st.radio("Show first", ["Largest decreases", "Largest increases"], horizontal=True)
    table = table.sort_values("recovery_pp", ascending=ordering == "Largest decreases")
    st.caption(
        f"{len(table)} eligible providers. All have 12 positive-activity months in each year. The volume threshold is a user-selected display rule, not a significance test."
    )
    if table.empty:
        st.info(
            "No providers meet this volume threshold and region selection. Lower the threshold or select all regions."
        )
    else:
        top = table.head(12).copy()
        top["Provider"] = top.org_name.str.title()
        fig = px.bar(
            top.sort_values("recovery_pp"),
            x="recovery_pp",
            y="Provider",
            orientation="h",
            labels={"recovery_pp": "Change (percentage points)"},
            color_discrete_sequence=["#167f86"],
            hover_data={
                "att_prior": ":,",
                "att_latest": ":,",
                "perf_prior_pct": ":.1f",
                "perf_latest_pct": ":.1f",
            },
        )
        fig.add_vline(x=0, line_color="#597083")
        st.plotly_chart(style_chart(fig, 450), use_container_width=True)
        columns = [
            "org_code",
            "org_name",
            "perf_prior_pct",
            "perf_latest_pct",
            "recovery_pp",
            "att_prior",
            "att_latest",
            "months_prior",
            "months_latest",
            "names_in_window",
        ]
        st.dataframe(table[columns].round(2), hide_index=True, width="stretch")
        st.download_button(
            "Download comparison table",
            table.to_csv(index=False),
            "ae-provider-comparison.csv",
            "text/csv",
        )
        st.info(
            "Do not read this as a ranking of care quality. There is no case-mix adjustment. A stable organisation code does not guarantee unchanged services; names_in_window flags some changes, not all mergers."
        )
with t_quality:
    st.subheader("Trace every number back to a source")
    st.success(
        f"{quality['source_files']} source files checked · {quality['national_reconciliation_checks']} provider-to-England reconciliations passed"
    )
    st.write(
        "The build stops on changed source bytes, malformed rows, unexpected columns, invalid counts, duplicates or totals that do not reconcile. A failed build leaves the previous database intact."
    )
    for notice in quality["notices"]:
        st.caption(notice)
    with st.expander("Validation rules", expanded=False):
        st.write(quality["checks"])
    st.dataframe(pd.DataFrame(manifest["sources"]), hide_index=True, width="stretch")
    st.download_button(
        "Download source manifest",
        json.dumps(manifest, indent=2),
        "source-manifest.json",
        "application/json",
    )
    st.markdown("**Metric definitions**")
    st.markdown(
        "- **Within four hours:** `(attendances − over-four-hour attendances) / attendances`. Zero attendances gives no rate.\n- **Type 1:** major consultant-led A&E departments.\n- **All types:** Type 1 + Type 2 + other A&E departments; booked appointments excluded.\n- **Year-on-year:** same calendar month, not simply the twelfth earlier row.\n- **Comparisons:** percentages calculated from total counts, never averaged across providers.\n- **Unit:** provider organisation per month; not an individual hospital or patient."
    )
    st.caption(
        "Source files are pinned to a historical period. Later revisions may change the results. Public aggregate data only; no patient records, NHS systems access or clinical decisions."
    )
    st.markdown(
        "[Definitions and methodology in the repository](https://github.com/abasukanga4/nhs-ae-sql/blob/main/docs/METHODS.md) · [Tableau export guide](https://github.com/abasukanga4/nhs-ae-sql/blob/main/docs/TABLEAU.md)"
    )
