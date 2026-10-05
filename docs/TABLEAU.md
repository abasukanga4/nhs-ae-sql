# Reuse the reporting data in Tableau

This repository includes an export and calculation guide, **not a completed Tableau workbook**. The interactive application is built with Streamlit. The exported files are public aggregate data suitable for a separate Tableau practice workbook.

## Connect

1. Connect Tableau to the text file `data/demo/providers.csv`.
2. Set `period_month` to Date, `org_code` / `org_name` / `region` to String, and attendance/wait columns to whole numbers.
3. Use the provider table alone. Do not union `national.csv` into it: doing so would double-count England activity. For a national reference, use a separate worksheet/data source or an explicit monthly relationship with a documented level of detail.
4. Filter to one provider code, or clearly label a multi-provider aggregate. Use code rather than name as the longitudinal identifier; review reorganisations separately.

## Calculated fields

**Type 1 within four hours** (format as Percentage):

```text
IF SUM([att_type1]) > 0 THEN
    1 - SUM([over4hr_type1]) / SUM([att_type1])
END
```

**All types within four hours** (format as Percentage):

```text
IF SUM([att_all]) > 0 THEN
    1 - SUM([over4hr_all]) / SUM([att_all])
END
```

Use summed counts at the view's level of detail. Do not use `AVG([perf_type1])` to combine months or providers. These formulas return fractions; formatting as a percentage is sufficient, without also multiplying by 100.

For the two-year comparison, connect separately to `reports/provider_comparison.csv`. `perf_prior_pct` and `perf_latest_pct` already contain values on a **0–100 scale**: format as numbers with a `%` suffix, not Tableau's percentage format. `recovery_pp` is a difference in percentage points, not a percent change. This exported table has the default 60,000-attendances rule applied to both complete years.

## Suggested dashboard

- Provider and date filters.
- Three KPI cards: attendances, within-four-hour percentage, over-four-hour count.
- A monthly line chart and an attendance bar chart with aligned dates.
- A comparison sheet using the precomputed complete-year table, with both denominators shown in its tooltip.
- A visible definition/source note and the historical snapshot dates.

A date filter changes the KPI aggregation but should not silently redefine the precomputed annual comparison. Label the fixed annual windows beside that sheet.

## Reconcile before sharing

With all providers included, Type 1, April 2025–March 2026, check **16,744,864 attendances** and **60.556473% within four hours**. For March 2026 alone, check **1,451,010 attendances** and **63.888188%**. Match these to the separate national SQL output before styling the workbook. Do not add the national rows to the provider rows.

For missing dates, a Tableau table calculation based on previous rows can compare the wrong period. This project's SQL output already performs a calendar-date join; use its exported `yoy_pp` for a selected provider or create a properly tested date scaffold before rebuilding that logic in Tableau.

References: Tableau's official [calculated fields](https://help.tableau.com/current/pro/desktop/en-us/calculations_calculatedfields_formulas.htm) and [aggregate calculations](https://help.tableau.com/current/pro/desktop/en-us/calculations_calculatedfields_aggregate_create.htm) documentation.
