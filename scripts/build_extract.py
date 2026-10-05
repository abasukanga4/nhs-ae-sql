"""Create the local Tableau extract from the checked public provider snapshot."""

import csv
from datetime import date
from pathlib import Path

from tableauhyperapi import (
    Connection,
    CreateMode,
    HyperProcess,
    Inserter,
    SqlType,
    TableDefinition,
    TableName,
    Telemetry,
)

ROOT = Path(__file__).resolve().parents[1]


def build():
    rows = list(csv.DictReader((ROOT / "data/demo/providers.csv").open()))
    types = {
        k: SqlType.date()
        if k == "period_month"
        else SqlType.text()
        if k in {"org_code", "org_name", "region"}
        else SqlType.double()
        if k.startswith("perf_")
        else SqlType.big_int()
        for k in rows[0]
    }
    table = TableDefinition(
        TableName("Extract", "Extract"), [TableDefinition.Column(k, t) for k, t in types.items()]
    )
    out = ROOT / "bi/Data/Extracts/providers.hyper"
    out.parent.mkdir(parents=True, exist_ok=True)
    with (
        HyperProcess(
            Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU, parameters={"log_config": ""}
        ) as process,
        Connection(process.endpoint, out, CreateMode.CREATE_AND_REPLACE) as conn,
    ):
        conn.catalog.create_schema("Extract")
        conn.catalog.create_table(table)
        values = []
        for row in rows:
            values.append(
                [
                    None
                    if row[k] == ""
                    else date.fromisoformat(row[k])
                    if k == "period_month"
                    else row[k]
                    if k in {"org_code", "org_name", "region"}
                    else float(row[k])
                    if k.startswith("perf_")
                    else int(row[k])
                    for k in types
                ]
            )
        with Inserter(conn, table) as inserter:
            inserter.add_rows(values)
            inserter.execute()
        assert conn.execute_scalar_query('SELECT COUNT(*) FROM "Extract"."Extract"') == 4758
        print("Extract checked: 4,758 provider-months")


if __name__ == "__main__":
    build()
