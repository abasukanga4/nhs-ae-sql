"""Build the portable native Tableau workbook from the checked provider snapshot."""

from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NS = "http://www.tableausoftware.com/xml/user"
ET.register_namespace("user", NS)


def sub(parent, tag, text=None, **attrs):
    node = ET.SubElement(parent, tag, {k.replace("_", "-"): str(v) for k, v in attrs.items()})
    if text is not None:
        node.text = text
    return node


def build():
    source = ROOT / "data/demo/providers.csv"
    with source.open() as handle:
        rows = list(csv.DictReader(handle))
    wb = ET.Element(
        "workbook",
        {
            "original-version": "10.5",
            "source-build": "10.5.0",
            "source-platform": "mac",
            "version": "10.5",
        },
    )
    datasources = sub(wb, "datasources")
    params = sub(
        datasources,
        "datasource",
        name="Parameters",
        inline="true",
        hasconnection="false",
        version="10.5",
    )
    provider_choices = ["All providers"] + sorted({r["org_code"] for r in rows})
    for name, caption, default, choices in [
        ("Provider", "Provider code", "All providers", provider_choices),
        ("Department", "Department type", "Type 1", ["Type 1", "All types"]),
        ("Window", "Reporting window", "Latest 12 months", ["Full 24 months", "Latest 12 months"]),
    ]:
        col = sub(
            params,
            "column",
            name=f"[{name}]",
            caption=caption,
            datatype="string",
            role="measure",
            type="nominal",
            param_domain_type="list",
            value='"' + default + '"',
        )
        sub(col, "calculation", **{"class": "tableau", "formula": '"' + default + '"'})
        members = sub(col, "members")
        for value in choices:
            sub(members, "member", value='"' + value + '"')
    ds = sub(
        datasources,
        "datasource",
        name="provider_data",
        caption="NHS England provider-months",
        inline="true",
        version="10.5",
    )
    conn = sub(
        ds,
        "connection",
        **{
            "class": "textscan",
            "directory": "Data",
            "filename": "providers.csv",
            "password": "",
            "server": "",
        },
    )
    rel = sub(conn, "relation", name="providers", table="[providers.csv]", type="table")
    cols = sub(rel, "columns", character_set="UTF-8", header="yes", locale="en_GB", separator=",")
    fields = {
        k: (
            "date"
            if k == "period_month"
            else "string"
            if k in {"org_code", "org_name", "region"}
            else "real"
            if k.startswith("perf_")
            else "integer"
        )
        for k in rows[0]
    }
    for i, (name, dtype) in enumerate(fields.items()):
        sub(cols, "column", name=name, datatype=dtype, ordinal=i)
        field = sub(
            ds,
            "column",
            name=f"[{name}]",
            caption=name.replace("_", " ").title(),
            datatype=dtype,
            role="dimension" if dtype in {"date", "string"} else "measure",
            type="ordinal"
            if dtype == "date"
            else "nominal"
            if dtype == "string"
            else "quantitative",
        )
        if dtype == "date":
            field.set("default-format", "dmmm yy")
    formulas = {
        "Selected attendances": "IF [Parameters].[Department] = 'Type 1' THEN [att_type1] ELSE [att_all] END",
        "Selected over four hours": "IF [Parameters].[Department] = 'Type 1' THEN [over4hr_type1] ELSE [over4hr_all] END",
        "Within four hours": "IF SUM([Selected attendances]) > 0 THEN 1 - SUM([Selected over four hours]) / SUM([Selected attendances]) END",
        "Provider selected": "([Parameters].[Provider] = 'All providers' OR [org_code] = [Parameters].[Provider]) AND [Selected attendances] > 0 AND ([Parameters].[Window] = 'Full 24 months' OR [period_month] >= #2025-04-01#)",
    }
    for name, formula in formulas.items():
        boolean = name == "Provider selected"
        col = sub(
            ds,
            "column",
            name=f"[{name}]",
            datatype="boolean" if boolean else "real",
            role="dimension" if boolean else "measure",
            type="nominal" if boolean else "quantitative",
        )
        sub(col, "calculation", **{"class": "tableau", "formula": formula})
        if name == "Within four hours":
            col.set("default-format", "p0.0%")
    extract = sub(ds, "extract", count="4758", enabled="true", units="records")
    extract_conn = sub(
        extract,
        "connection",
        **{
            "class": "hyper",
            "dbname": "Data/Extracts/providers.hyper",
            "schema": "Extract",
            "tablename": "Extract",
            "access_mode": "readonly",
            "authentication": "auth-none",
        },
    )
    sub(extract_conn, "relation", name="Extract", table="[Extract].[Extract]", type="table")
    sheets = sub(wb, "worksheets")
    specs = [
        ("Monthly performance", "period_month", "Within four hours", "Line"),
        ("Monthly attendances", "period_month", "Selected attendances", "Bar"),
        ("Provider comparison", "org_code", "Within four hours", "Bar"),
    ]
    for name, dimension, measure, mark in specs:
        sheet = sub(sheets, "worksheet", name=name)
        table = sub(sheet, "table")
        view = sub(table, "view")
        sources = sub(view, "datasources")
        sub(sources, "datasource", name="provider_data", caption="NHS England provider-months")
        deps = sub(view, "datasource-dependencies", datasource="provider_data")
        for col in list(ds.findall("column")):
            deps.append(ET.fromstring(ET.tostring(col)))
        dim = "none:" + dimension + (":qk" if dimension == "period_month" else ":nk")
        sub(
            deps,
            "column-instance",
            column=f"[{dimension}]",
            derivation="None",
            name=f"[{dim}]",
            pivot="key",
            type="quantitative" if dimension == "period_month" else "nominal",
        )
        aggregate = "usr" if measure == "Within four hours" else "sum"
        metric = aggregate + ":" + measure + ":qk"
        sub(
            deps,
            "column-instance",
            column=f"[{measure}]",
            derivation="User" if aggregate == "usr" else "Sum",
            name=f"[{metric}]",
            pivot="key",
            type="quantitative",
        )
        sub(
            deps,
            "column-instance",
            column="[Provider selected]",
            derivation="None",
            name="[none:Provider selected:nk]",
            pivot="key",
            type="nominal",
        )
        filt = sub(
            view,
            "filter",
            **{"class": "categorical", "column": "[provider_data].[none:Provider selected:nk]"},
        )
        sub(
            filt,
            "groupfilter",
            function="member",
            level="[none:Provider selected:nk]",
            member="true",
        )
        sub(view, "aggregation", value="true")
        style = sub(table, "style")
        rule = sub(style, "style-rule", element="mark")
        sub(rule, "format", attr="mark-color", value="#147d92")
        pane = sub(sub(table, "panes"), "pane")
        sub(sub(pane, "view"), "breakdown", value="auto")
        sub(pane, "mark", **{"class": mark})
        if dimension == "org_code":
            sub(table, "rows", f"[provider_data].[{dim}]")
            sub(table, "cols", f"[provider_data].[{metric}]")
        else:
            sub(table, "rows", f"[provider_data].[{metric}]")
            sub(table, "cols", f"[provider_data].[{dim}]")
    dashboards = sub(wb, "dashboards")
    dash = sub(dashboards, "dashboard", name="Hospital performance")
    sub(dash, "style")
    sub(
        dash,
        "size",
        sizing_mode="fixed",
        minwidth="1200",
        maxwidth="1200",
        minheight="760",
        maxheight="760",
    )
    zones = sub(dash, "zones")
    title = sub(zones, "zone", id="1", type="text", x="2000", y="1500", w="95000", h="10000")
    ft = sub(title, "formatted-text")
    sub(
        ft,
        "run",
        "HOSPITAL PERFORMANCE EXPLORER\nNHS England public aggregates · April 2024–March 2026",
        bold="true",
        fontsize="17",
    )
    for i, (name, x, y, w, h) in enumerate(
        [
            ("Monthly performance", 2000, 25000, 55000, 27000),
            ("Monthly attendances", 2000, 55000, 55000, 27000),
            ("Provider comparison", 60000, 25000, 38000, 57000),
        ],
        2,
    ):
        sub(zones, "zone", id=i, name=name, x=x, y=y, w=w, h=h)
    for i, p in enumerate(["Provider", "Department", "Window"]):
        sub(
            zones,
            "zone",
            id=20 + i,
            type="paramctrl",
            param=f"[Parameters].[{p}]",
            mode="compact",
            x=2000 + i * 32000,
            y=14500,
            w=30000,
            h=8500,
        )
    note = sub(zones, "zone", id="8", type="text", x="2000", y="86500", w="96000", h="10000")
    sub(
        sub(note, "formatted-text"),
        "run",
        "Four hours: arrival to admission, transfer or discharge. Rates are calculated from summed counts. Provider organisations can cover multiple sites. Historical, descriptive comparisons; no case-mix adjustment. Use the controls above. Only providers with activity in the selected department are included. Provider codes identify organisations, not individual hospitals.",
        fontsize="11",
    )
    windows = sub(wb, "windows", source_height="30")
    for name, _, _, _ in specs:
        window = sub(windows, "window", **{"class": "worksheet", "name": name})
        cards = sub(window, "cards")
        edge = sub(cards, "edge", name="left")
        strip = sub(edge, "strip", size="190")
        for typename in ["pages", "filters", "marks"]:
            sub(strip, "card", type=typename)
        for p in ["Provider", "Department", "Window"]:
            sub(strip, "card", type="parameter", param=f"[Parameters].[{p}]")
        top = sub(cards, "edge", name="top")
        for card in ["columns", "rows", "title"]:
            sub(sub(top, "strip", size="30"), "card", type=card)
        sub(window, "viewpoint")
    dashboard_window = sub(
        windows,
        "window",
        **{"class": "dashboard", "maximized": "true", "name": "Hospital performance"},
    )
    viewpoints = sub(dashboard_window, "viewpoints")
    for name, _, _, _ in specs:
        sub(viewpoints, "viewpoint", name=name)
    sub(dashboard_window, "active", id="2")
    sub(dashboard_window, "device-preview")
    ET.indent(wb)
    out = ROOT / "bi"
    out.mkdir(exist_ok=True)
    raw = ET.tostring(wb, encoding="utf-8", xml_declaration=True)
    (out / "Hospital Performance Explorer.twb").write_bytes(raw)
    (out / "Data").mkdir(exist_ok=True)
    (out / "Data/providers.csv").write_bytes(source.read_bytes())
    with zipfile.ZipFile(
        out / "Hospital Performance Explorer.twbx", "w", zipfile.ZIP_DEFLATED
    ) as z:
        for name, content in [
            ("Hospital Performance Explorer.twb", raw),
            ("Data/providers.csv", source.read_bytes()),
            ("Data/Extracts/providers.hyper", (out / "Data/Extracts/providers.hyper").read_bytes()),
        ]:
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 5, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, content)
    target = [r for r in rows if "2025-04-01" <= r["period_month"] <= "2026-03-01"]
    att = sum(int(r["att_type1"]) for r in target)
    over = sum(int(r["over4hr_type1"]) for r in target)
    checks = {
        "status": "Build checks only; see validation.json for native review evidence",
        "provider_rows": len(rows),
        "provider_month_key_unique": len({(r["org_code"], r["period_month"]) for r in rows})
        == len(rows),
        "reconciliation": {
            "window": "2025-04 to 2026-03",
            "type1_attendances": att,
            "type1_within_four_hours": 1 - over / att,
        },
        "worksheets": [s[0] for s in specs],
        "parameters": ["Provider code", "Department type"],
    }
    assert (
        att == 16744864
        and abs(checks["reconciliation"]["type1_within_four_hours"] - (1 - 6604765 / 16744864))
        < 1e-9
    )
    checks["parameters"] = ["Provider code", "Department type", "Reporting window"]
    # A rebuild must not overwrite the separately recorded native review evidence.
    (out / "build-checks.json").write_text(json.dumps(checks, indent=2) + "\n")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    build()
