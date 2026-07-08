-- ============================================================================
-- 03_analysis_seasonality.sql
-- Q: "Is winter pressure structural or seasonal?" — at the England national
--    level, across both winters in the data.
-- ============================================================================
-- Definitions
--   * Winter    = December, January, February (the NHS "winter pressures"
--                 window). Everything else = "rest of year".
--   * Seasonal  => performance dips each winter but recovers the next spring
--                  to roughly its previous level (a repeating cycle).
--   * Structural=> the winter floor ratchets DOWN year on year, i.e. the
--                  system does not fully bounce back.
--
-- The final result set is the national monthly trace enriched with:
--   * rolling 3-month average performance  -> AVG(...) OVER (... ROWS ...)
--   * year-on-year change                  -> LAG(perf, 12) OVER (...)
--   * next-month change                    -> LEAD(perf, 1)  OVER (...)
--   * a percentile rank of each month       -> PERCENT_RANK() OVER (...)
--   * a winter flag + the winter/rest split labels
-- Python reads this to draw the national line with a rolling average and
-- winter shading, and to print the winter-vs-rest comparison.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. base: national series with a winter flag and a "winter season" label
--    (a winter spans two calendar years, e.g. Dec-2024..Feb-2025 = 'W2024-25').
-- ----------------------------------------------------------------------------
WITH base AS (
    SELECT
        period_month,
        perf_all,
        perf_type1,
        month(period_month) AS mth,
        (month(period_month) IN (12, 1, 2)) AS is_winter,
        CASE
            WHEN month(period_month) = 12 THEN 'W' || year(period_month) || '-' || right((year(period_month) + 1)::VARCHAR, 2)
            WHEN month(period_month) IN (1, 2) THEN 'W' || (year(period_month) - 1) || '-' || right(year(period_month)::VARCHAR, 2)
        END AS winter_season
    FROM ae_national
),

-- ----------------------------------------------------------------------------
-- 2. traced: layer on the window functions over the ordered monthly series.
-- ----------------------------------------------------------------------------
traced AS (
    SELECT
        period_month,
        perf_all,
        perf_type1,
        is_winter,
        winter_season,
        -- rolling 3-month average (this month + 2 prior) smooths the monthly noise
        AVG(perf_all) OVER (
            ORDER BY period_month
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ) AS perf_all_roll3,
        AVG(perf_type1) OVER (
            ORDER BY period_month
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ) AS perf_type1_roll3,
        -- year-on-year change: this month vs the same month 12 rows back
        perf_all   - LAG(perf_all,   12) OVER (ORDER BY period_month) AS yoy_all,
        perf_type1 - LAG(perf_type1, 12) OVER (ORDER BY period_month) AS yoy_type1,
        -- next month's change (does spring recover after the winter trough?)
        LEAD(perf_all, 1) OVER (ORDER BY period_month) - perf_all AS next_month_delta_all,
        -- where does this month sit in the whole distribution? (0 = worst, 1 = best)
        PERCENT_RANK() OVER (ORDER BY perf_all) AS perf_all_pctile
    FROM base
)

-- ----------------------------------------------------------------------------
-- Final result set: the enriched national monthly trace.
-- All percentages are scaled to points for readability.
-- ----------------------------------------------------------------------------
SELECT
    period_month,
    round(perf_all        * 100, 2) AS perf_all_pct,
    round(perf_type1      * 100, 2) AS perf_type1_pct,
    round(perf_all_roll3  * 100, 2) AS perf_all_roll3_pct,
    round(perf_type1_roll3 * 100, 2) AS perf_type1_roll3_pct,
    is_winter,
    winter_season,
    round(yoy_all   * 100, 2) AS yoy_all_pp,
    round(yoy_type1 * 100, 2) AS yoy_type1_pp,
    round(perf_all_pctile, 3) AS perf_all_pctile
FROM traced
ORDER BY period_month;

-- >>> RESULT: winter_summary
-- ----------------------------------------------------------------------------
-- Companion aggregate: winter-vs-rest comparison used to judge seasonal vs
-- structural. Groups the national series into each winter season and the
-- rest-of-year, and reports the mean and (via PERCENTILE_CONT) the median
-- performance plus the worst month in each group. If the winter FLOOR rises
-- season-on-season the pressure is recovering (structural improvement), not
-- ratcheting down.
-- ----------------------------------------------------------------------------
WITH b AS (
    SELECT
        perf_all,
        perf_type1,
        (month(period_month) IN (12, 1, 2)) AS is_winter,
        CASE
            WHEN month(period_month) = 12 THEN 'W' || year(period_month) || '-' || right((year(period_month) + 1)::VARCHAR, 2)
            WHEN month(period_month) IN (1, 2) THEN 'W' || (year(period_month) - 1) || '-' || right(year(period_month)::VARCHAR, 2)
        END AS winter_season
    FROM ae_national
)
SELECT
    CASE WHEN is_winter THEN winter_season ELSE 'rest-of-year' END AS grp,
    count(*)                                                       AS n_months,
    round(avg(perf_all)   * 100, 2)                               AS mean_all_pct,
    round(avg(perf_type1) * 100, 2)                               AS mean_type1_pct,
    -- median via PERCENTILE_CONT (continuous interpolation)
    round(percentile_cont(0.5) WITHIN GROUP (ORDER BY perf_all) * 100, 2) AS median_all_pct,
    round(min(perf_all)   * 100, 2)                               AS worst_month_all_pct
FROM b
GROUP BY 1
ORDER BY (grp = 'rest-of-year'), grp;   -- winters first, then rest-of-year
