# Definitions, model and validation

## Source and reporting grain

The source is NHS England's monthly **A&E Attendances and Emergency Admissions** CSV publication:

- [2024–25 source page](https://www.england.nhs.uk/statistics/statistical-work-areas/ae-waiting-times-and-activity/ae-attendances-and-emergency-admissions-2024-25/)
- [2025–26 source page](https://www.england.nhs.uk/statistics/statistical-work-areas/ae-waiting-times-and-activity/ae-attendances-and-emergency-admissions-2025-26/)
- [Publisher's definitions](https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2025/11/AE-Attendances-Emergency-Definitions-v5.0-final-August-2020.pdf)

A provider row represents one **organisation and reporting month**, not a patient or necessarily a single hospital. The natural key is `(period_month, org_code)`. The national `TOTAL` row lives in a separate table so it cannot accidentally be added to the provider totals.

`data/source_manifest.json` records the exact URL and SHA-256 for each month. The reporting month comes from that reviewed manifest; each provider's source Period must agree. The national row's Period is not a usable date. The source header contract is in `data/source_columns.json`.

## Metric dictionary

| Field | Meaning / rule |
|---|---|
| `att_type1` | Unplanned attendances at major consultant-led Type 1 A&E departments. |
| `att_all` | Type 1 + Type 2 + other unplanned attendances; booked appointments excluded. |
| `over4hr_type1`, `over4hr_all` | Corresponding attendances with total time over four hours. |
| `perf_type1`, `perf_all` | Fractions: `1 - over4hr / attendances`; null when the denominator is zero. |
| `within_4h_pct` | The selected department's fraction multiplied by 100. |
| `waited_4_12hr_dta`, `waited_12hr_dta` | Wait from decision to admit to admission; this is not the clock from arrival. |
| `yoy_pp` | Current monthly percentage minus the percentage for the same calendar month a year earlier. |
| `rolling_3m_pct` | Rate from summed counts over three calendar months, emitted only with three monthly observations. |
| `recovery_pp` | Historical column name retained for the descriptive change between the latest and prior 12-month rates. It does not imply a causal recovery effect. |
| `names_in_window` | Number of source names seen under an organisation code; a review flag, not a complete merger detector. |

The four-hour interval is arrival to admission, transfer or discharge. It is not time to first assessment. Attendance counts describe visits, not unique people.

## Aggregation and comparison

For any window: `100 * (1 - SUM(over4hr_type1) / NULLIF(SUM(att_type1), 0))`. Monthly percentages are not averaged: doing so gives a quiet month the same weight as a busy one.

`monthly()` uses an explicit date join for year-on-year changes. A missing month cannot accidentally turn a twelfth-previous-row comparison into the wrong calendar month. Its rolling window covers the current and preceding two calendar months. Zero attendance yields no monthly rate; a multi-month window can still have a rate if total activity is positive.

The comparison query is anchored to the latest source month. It requires 12 positive-activity months in **each** of two adjacent years and applies the same attendance threshold to both years. The default 60,000 threshold is a display rule, not an official NHS threshold or a significance criterion. The dashboard's chart month selector does not change these comparison windows.

Organisation codes and names do not prove stable clinical services. Comparisons have no adjustment for case mix, acuity, service configuration or deprivation. The output must not be presented as a ranking of care quality.

## Ingestion checks and failure behaviour

1. The manifest must contain an ordered, unique, complete sequence of reporting months.
2. Each downloaded or local source must match its pinned SHA-256.
3. The first 22 headers must match the published schema exactly. Extra columns are only accepted if every extra data cell is empty, and that exception is recorded.
4. Every row must have the expected width, nonblank organisation code/name and a unique code within its month.
5. All 18 source count columns must be nonnegative integers (correct thousands separators accepted). Blanks, suppression markers, fractions and unknown strings stop the build; they are not changed to zero.
6. Each over-four-hour count must be no greater than its corresponding attendance count.
7. One national total and at least one provider must exist in every source month.
8. The six clean count measures must sum from provider rows to the national total in every month.

The build takes place in a temporary DuckDB file. Only a successful build replaces the existing database. Downloaded files are validated as a batch before replacing the local source copies. The quality report records the checked manifest and database hashes.

Exporting verifies those hashes first. The dashboard then checks its committed CSVs, quality report and source manifest against `data/demo/snapshot.json` before opening them. These controls catch accidental inconsistencies and source revisions; they are not a cryptographic trust service and do not audit how trusts collected their underlying data.

## Tests and reproducibility

`pytest -q` covers invalid counts, changed headers, row-width errors, duplicate keys, mismatched periods, populated extra columns, impossible counts, missing months, national reconciliation failure, and preservation of a previous database. Reporting tests check weighted rates, missing-month year-on-year behaviour, zero denominators and incomplete provider years. Streamlit tests exercise the default view, a selected trust, all-types reporting and an empty comparison.

The suite uses small synthetic fixtures for failure cases and the committed public aggregate snapshot for integration checks. It does not require network access. Updating the source period is a reviewed maintenance change: update the manifest, rebuild exports, revisit the date labels and findings, and rerun the tests.
