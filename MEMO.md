# England A&E reporting brief

**Question:** how has reported time in A&E changed nationally, how much variation is visible between providers, and what should be investigated next?

**Scope:** NHS England aggregate returns, April 2024–March 2026. An independent historical analysis for an operational reporting audience, designed to work across England rather than for a particular trust. Findings are reproduced in `reports/findings.json` and `reports/provider_comparison.csv` by `python run_analysis.py`.

## National findings

| Measure | April 2024–March 2025 | April 2025–March 2026 |
|---|---:|---:|
| Type 1 attendances | 16,396,174 | 16,744,864 |
| Type 1 within four hours | 58.98% | 60.56% |
| All A&E types within four hours | 73.32% | 74.37% |

The Type 1 annual proportion was **1.58 percentage points higher** in the latest year, while reported activity also increased. Annual percentages use summed counts, not the mean of monthly percentages.

For March 2026 alone, Type 1 performance was **63.89%**, compared with **60.61% in March 2025**: a change of **+3.28 percentage points**. The all-types March 2026 measure was **76.63%**. A monthly result and a full-year result answer different questions, and the difference between Type 1 and all types makes the department definition essential to any briefing.

These movements do not identify why performance changed. The extract has no staffing, bed availability, patient acuity or individual outcomes data. It cannot demonstrate that a particular intervention caused an improvement.

## Provider variation

At the default threshold of 60,000 Type 1 attendances in each year, **113 providers** have 12 positive-activity months in both comparison windows. **77** have a higher annual within-four-hour proportion and **36** have a lower one. The dashboard can filter this comparison by region and activity threshold, and inspect each provider's monthly context.

These counts describe the selected, complete-reporting cohort. They are not counts of clinically better or worse providers. The threshold is a reporting choice, not a statistical significance test. England is contextual information, not a risk-adjusted benchmark for a particular trust.

## Questions for an operational meeting

1. Did service boundaries, coding or submission practices change during the period? Check this before interpreting a movement as operational improvement.
2. Which sites, arrival patterns or patient pathways contributed to a local change? This aggregate extract cannot answer that; it would need appropriate local reporting access.
3. Did demand, staffing or bed availability change at the same time? These variables are absent here, so causal explanations remain untested.
4. Does a longer series show the same pattern? Two winters are too few to separate seasonality from structural change reliably.

The immediate next action is to select a provider or region, confirm the interpretation with reporting and operational colleagues, then agree a focused follow-up analysis. This dataset alone does not support a recommendation to redistribute resources or copy an intervention between trusts.

## Reporting assurance

All 24 pinned source files passed schema, period, count, uniqueness and source-hash checks. Six count measures reconcile from providers to England for every month (**144 reconciliations**). One file has six surplus columns that were confirmed empty for every data row. Details are in `reports/quality.json` and [the methods](docs/METHODS.md).

Later revisions can change these results. Counts of attendances are not counts of unique patients. Provider organisations can cover multiple hospital sites. Decision-to-admit waits must not be interpreted as time since arrival. No patient-level information, NHS systems access or clinical recommendations are involved.
