# A two-minute project walkthrough

This is a guide to understanding and demonstrating the project. It describes implemented work, not NHS employment, production deployment or clinical experience.

## 1. Start with the reporting question

Open the dashboard at England and Type 1. Explain that the question is whether reported time in A&E has changed and what an operational team should investigate. State the historical dates and organisation-level grain.

## 2. Explain one finding

March 2026 was 63.89% within four hours, up 3.28 percentage points from March 2025. The annual comparison is more modest: 60.56% versus 58.98%, or +1.58 percentage points. Explain why a single month and a whole year answer different questions.

Do not say the dashboard proves a staffing change worked or that one trust provides better clinical care. Those claims need evidence absent from this dataset.

## 3. Show the calculation and checks

Open `nhs_ae/reporting.py` and `sql/03_analysis_recovery.sql`. Explain why rates use summed counts, why year-on-year joins match dates, and why incomplete years are excluded from the comparison.

Switch to a provider of interest to demonstrate the same reusable reporting logic. Then show Data checks & methods. Trace a figure to the source manifest and explain what happens if a count is missing or a file changes: the pipeline stops, and the previous database is preserved.

## 4. Close with a useful next step

Download a monthly extract and a briefing. Explain that the next step would be to confirm reporting/service changes with colleagues before seeking more detailed local data. Demonstrate what can be inferred and what cannot.

## Questions to be able to answer yourself

- What is the difference between a percentage-point change and a percent change?
- Why can averaging monthly percentages be misleading?
- What does a zero denominator mean? Why is a missing count different from zero?
- What would happen after a trust merger or an official data revision?
- Why are 12-hour decision-to-admit waits different from 12 hours since arrival?
- Which requirements are demonstrated here, and which still need practice (for example, building a native Tableau workbook or working with an EPR system)?

A strong explanation of one query and one validation failure is more useful than listing tools without being able to discuss the trade-offs.
