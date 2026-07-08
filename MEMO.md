# A&E 4-hour performance: who is recovering, and is winter structural?

**For:** an NHS acute operations manager
**Data:** NHS England A&E Attendances & Emergency Admissions, monthly provider-level, **April 2024 – March 2026** (24 months, ~200 providers/month). 4-hour performance is defined as `1 − (attendances over 4 hours ÷ attendances)`, reported both for **all A&E types** and for **Type 1** (major, consultant-led departments, where the 4-hour target bites hardest).

## The question
Which acute NHS trusts are recovering fastest on the 4-hour A&E standard, and is winter pressure structural (a downward ratchet) or seasonal (a dip that recovers each spring)?

## Findings (all figures computed from the data)

1. **The system is recovering, modestly but broadly.** National all-types performance rose from **73.32%** in the prior 12 months to **74.37%** in the latest 12 months (+1.05pp, volume-weighted); Type 1 rose **58.98% → 60.56%** (+1.58pp). March 2026 (**76.63%**) is the single best month in the whole 24-month series, up from **74.39%** in March 2025.

2. **Recovery is uneven — it is a story of specific trusts, not a uniform tide.** Of **113** acute Type 1 trusts with material volume in both years, **77 improved** and **36 declined** year-on-year. The fastest recoverers are **The Princess Alexandra Hospital** (Type 1 49.0% → 67.4%, **+18.4pp**), **United Lincolnshire Hospitals** (44.8% → 60.2%, **+15.4pp**) and **Calderdale and Huddersfield** (69.2% → 83.4%, **+14.2pp**). At the other end, **Ashford and St Peter's** fell **−16.0pp** (66.7% → 50.8%).

3. **Winter pressure is seasonal, and the winter floor is *rising*, not ratcheting down.** Both winters (Dec–Feb) sit clearly below the rest of the year (mean **74.33%**), but the winter average improved from **71.88%** (W2024‑25) to **72.85%** (W2025‑26), and the worst month lifted from **70.46%** (Dec 2024) to **71.83%** (Jan 2026). Each winter dip is followed by a spring recovery. That is the signature of a *seasonal* pattern easing over time, **not** structural decline.

4. **Type 1 is where the strain concentrates.** The all-types figure (~74%) flatters the picture: Type 1 performance sits ~14 points lower (~60%) because Type 2 and walk-in/other units run near 100%. Any operational read of "the target" should track Type 1.

## Limitations (read before quoting these numbers)
- **Data revisions.** Many months here are the NHS England *revised* republications; earlier provisional figures differ. The pipeline pins the exact source file per month (`data/raw/download.sh`) so the numbers are reproducible, but they are point-in-time.
- **Provider mix changes.** The provider count drifts (198–202/month) as sites open, close or reorganise. The recovery ranking mitigates this by requiring a trust to have ≥60k Type 1 attendances in *both* comparison years, but merged/renamed trusts can still distort a single trust's trend.
- **Type 1 vs all-types.** The two views answer different questions; do not mix them. Recovery is ranked on Type 1 (the target); the national seasonality trace is shown all-types (the headline the public sees) with Type 1 alongside.
- **Denominator caveat.** Performance excludes sites reporting zero attendances in a month (282 provider-months), and volume-weights the window aggregates rather than averaging monthly rates — a large department counts more than a small one, by design.

## Recommendation
Treat winter as a **known, plannable seasonal load, not an emergency** — the floor is already lifting. Concentrate scarce recovery support on the **36 declining Type 1 trusts** (bottom recovery quartile), and study the top recoverers — Princess Alexandra, United Lincolnshire, Calderdale & Huddersfield — for the operational changes behind double-digit gains, then port them to the laggards before the next Dec–Feb window.
