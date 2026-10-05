# Native Tableau workbook

Download **[Hospital Performance Explorer.twbx](../bi/Hospital%20Performance%20Explorer.twbx)** and open it in Tableau Public/Desktop. The packaged workbook includes the public CSV and a **Hyper extract**, so it does not need an account, database credentials or a connection to this computer to read the data. It does not need to be published to Tableau Public to open locally.

The checked snapshot covers **April 2024–March 2026** and contains **4,758 provider-months**. The workbook was opened in Tableau Public **2026.2.3 on Apple silicon** and all three charts rendered. The portable source uses the older 10.5 workbook format; Tableau displays an upgrade notice on first opening. Accepting that notice converts the document locally.

## Views and controls

- **Monthly performance:** the percentage of attendances completed within four hours, calculated from summed counts.
- **Monthly attendances:** the activity denominator for the same selection.
- **Provider comparison:** weighted performance over the selected window, listed alphabetically by organisation code. This is not a ranked hospital league table.
- **Provider code:** all providers or an individual reporting organisation. Look up codes in [providers.csv](../data/demo/providers.csv); names can change over time.
- **Department type:** major A&E (Type 1) or all A&E types.
- **Reporting window:** latest 12 months (April 2025–March 2026) or the full 24-month snapshot.

The default is all providers, Type 1 and the latest 12 months. Organisations with no activity in the selected department are excluded from the charts. Provider organisations can cover multiple sites. A name or code is not proof that an organisation's boundaries stayed unchanged.

The [Streamlit dashboard](../README.md#explore-it) provides the fuller reporting workflow, including briefing exports and complete-year comparisons. This native workbook is a separate, portable BI view of the same checked provider data.

## Metric definition

The calculated field returns a fraction and uses Tableau percentage formatting:

```text
IF SUM([Selected attendances]) > 0 THEN
    1 - SUM([Selected over four hours]) / SUM([Selected attendances])
END
```

It **does not average provider percentages**. Four hours means arrival to admission, transfer or discharge, not time to first assessment. The view uses provider rows only; adding the national rows would double-count activity. Comparisons are historical, descriptive and not adjusted for case mix.

## Reconciliation and review

| Selection | Attendances | Within four hours |
|---|---:|---:|
| All providers, Type 1, April 2025–March 2026 | 16,744,864 | 60.556473% |
| All providers, all types, April 2025–March 2026 | 26,969,593 | 74.366024% |
| All providers, Type 1, March 2026 | 1,451,010 | 63.888188% |

Automated checks compare every Hyper extract value against the reporting CSV, check the packaged relative paths, verify unique provider-month records and reconcile the default annual totals. The native smoke test confirmed the embedded data loaded and the charts rendered. **Interactive control click-through remains a review item:** the desktop automation connection stopped responding during that check. It is not recorded as a passed interaction test. Current evidence is in [validation.json](../bi/validation.json).

For a manual acceptance check, switch to all types and confirm the monthly counts increase; select an active provider such as R1H and confirm the comparison has one row; switch to the full window and confirm there are 24 monthly marks. Restore the default selection before saving.

## Rebuild

Use Python 3.12 and the pinned official Tableau Hyper API:

```bash
pip install -r requirements-dev.txt -r requirements-bi.txt
python scripts/build_extract.py
python scripts/build_tableau.py
pytest -q
```

The builder packages relative paths and a fixed archive timestamp. Rebuilding the Hyper file can change its internal binary metadata while preserving the checked table values. `build-checks.json` records automatic checks; `validation.json` is a separate dated review record, so a build does not silently overwrite native review evidence.

The workbook, CSV and extract contain only published aggregate data. There are no patient records, credentials or private filesystem paths.

References: Tableau's official [packaged workbooks](https://help.tableau.com/current/pro/desktop/en-us/save_savework_packagedworkbooks.htm), [aggregate calculations](https://help.tableau.com/current/pro/desktop/en-us/calculations_calculatedfields_aggregate_create.htm) and [Hyper API](https://tableau.github.io/hyper-db/docs/) documentation.
