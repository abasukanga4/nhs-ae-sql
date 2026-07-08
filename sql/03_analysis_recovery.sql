-- ============================================================================
-- 03_analysis_recovery.sql
-- Q: "Which acute NHS trusts are recovering fastest on the 4-hour A&E
--     standard?" — measured year-on-year so the ranking is not a seasonal
--     artefact (latest-12 months vs the prior-12 months).
-- ============================================================================
-- Approach
--   * Restrict to ACUTE, MAJOR (Type 1) providers: a trust only counts if it
--     ran a real Type 1 department in BOTH comparison windows with meaningful
--     volume. This strips out UTCs / walk-in centres whose "100%" performance
--     is trivial and would pollute a recovery ranking.
--   * Aggregate breaches and attendances over each 12-month window, then
--     compute window performance = 1 - breaches/attendances. Aggregating the
--     raw counts (not averaging monthly rates) correctly volume-weights.
--   * Recovery = latest-12 performance minus prior-12 performance, in
--     percentage points. Rank descending.
--
-- SQL techniques on show here:
--   * layered CTEs (5, each feeding the next)
--   * conditional aggregation with FILTER to pivot the two 12-month windows
--   * RANK() and DENSE_RANK() for the fastest-recoverer leaderboard
--   * NTILE(4) to band trusts into recovery quartiles
--   (rolling AVG-OVER, LAG/LEAD and PERCENTILE_CONT are showcased in the
--    companion file 03_analysis_seasonality.sql.)
-- ============================================================================

-- Latest month in the data drives both 12-month windows dynamically.
CREATE OR REPLACE TEMP MACRO latest_month() AS (
    SELECT max(period_month) FROM ae_provider
);

-- ----------------------------------------------------------------------------
-- 1. major_provider_months: Type 1 activity for acute providers only.
--    Keep months where the trust had a Type 1 department reporting volume.
-- ----------------------------------------------------------------------------
WITH major_provider_months AS (
    SELECT
        org_code,
        org_name,
        region,
        period_month,
        att_type1,
        over4hr_type1,
        perf_type1
    FROM ae_provider
    WHERE att_type1 > 0            -- ran a Type 1 (major) A&E that month
),

-- ----------------------------------------------------------------------------
-- 2. windowed: tag each month as belonging to the latest-12 or prior-12
--    window (or neither). Uses the dynamic latest_month() anchor.
-- ----------------------------------------------------------------------------
windowed AS (
    SELECT
        *,
        CASE
            WHEN period_month >  (latest_month() - INTERVAL 12 MONTH)
                 THEN 'latest_12'
            WHEN period_month >  (latest_month() - INTERVAL 24 MONTH)
             AND period_month <= (latest_month() - INTERVAL 12 MONTH)
                 THEN 'prior_12'
        END AS window_bucket
    FROM major_provider_months
),

-- ----------------------------------------------------------------------------
-- 3. window_perf: volume-weighted Type 1 performance per trust per window.
--    Pivot the two windows into columns with FILTER.
-- ----------------------------------------------------------------------------
window_perf AS (
    SELECT
        org_code,
        any_value(org_name) AS org_name,
        any_value(region)   AS region,
        -- attendances in each window (used as an eligibility volume gate)
        sum(att_type1) FILTER (WHERE window_bucket = 'latest_12') AS att_latest,
        sum(att_type1) FILTER (WHERE window_bucket = 'prior_12')  AS att_prior,
        -- volume-weighted performance = 1 - total breaches / total attendances
        1.0 - sum(over4hr_type1) FILTER (WHERE window_bucket = 'latest_12')
              / NULLIF(sum(att_type1) FILTER (WHERE window_bucket = 'latest_12'), 0)::DOUBLE
            AS perf_latest,
        1.0 - sum(over4hr_type1) FILTER (WHERE window_bucket = 'prior_12')
              / NULLIF(sum(att_type1) FILTER (WHERE window_bucket = 'prior_12'), 0)::DOUBLE
            AS perf_prior
    FROM windowed
    WHERE window_bucket IS NOT NULL
    GROUP BY org_code
),

-- ----------------------------------------------------------------------------
-- 4. eligible: keep genuine acute trusts present in BOTH windows with
--    material Type 1 volume (>= 60k Type 1 attendances/yr ~ 5k/month), so the
--    ranking reflects real acute recovery, not tiny-site noise.
-- ----------------------------------------------------------------------------
eligible AS (
    SELECT
        *,
        (perf_latest - perf_prior) AS recovery_pp   -- change in performance (as a proportion)
    FROM window_perf
    WHERE att_latest >= 60000
      AND att_prior  >= 60000
      AND perf_latest IS NOT NULL
      AND perf_prior  IS NOT NULL
)

-- ----------------------------------------------------------------------------
-- 5. Final leaderboard: rank, dense_rank and recovery quartile band.
--    recovery_pp is scaled to percentage points for readability.
-- ----------------------------------------------------------------------------
SELECT
    RANK()       OVER (ORDER BY recovery_pp DESC) AS recovery_rank,
    DENSE_RANK() OVER (ORDER BY recovery_pp DESC) AS recovery_dense_rank,
    NTILE(4)     OVER (ORDER BY recovery_pp DESC) AS recovery_quartile,  -- 1 = fastest-recovering quarter
    org_code,
    org_name,
    region,
    round(perf_prior  * 100, 1) AS perf_prior_pct,
    round(perf_latest * 100, 1) AS perf_latest_pct,
    round(recovery_pp * 100, 1) AS recovery_pp,
    att_latest
FROM eligible
ORDER BY recovery_pp DESC;
