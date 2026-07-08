-- ============================================================================
-- 02_cleaning.sql — transform staging text into typed, analysis-ready tables
-- ============================================================================
-- Runs AFTER load.py has populated stg_ae_raw from all 24 CSVs.
-- Everything here is set-based SQL; load.py adds no transform logic.
--
-- Responsibilities:
--   1. Parse the reporting month as a real DATE (from the filename label).
--   2. Cast text measures to integers defensively (strip thousands commas,
--      treat blanks as NULL) even though the current source is plain ints —
--      this makes the pipeline robust to the formatting the brief warned about.
--   3. Split the single national TOTAL row out from the provider rows.
--   4. Derive the 4-hour performance metrics = 1 - breaches / attendances.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Reusable macros. to_int handles the defensive casting once, everywhere:
--   * NULLIF(trim(x),'')     -> blank / whitespace becomes NULL
--   * replace(...,',','')    -> strip thousands separators if ever present
--   * TRY_CAST ... AS BIGINT -> anything still unparseable becomes NULL
--     rather than throwing, so one dirty cell can't abort the whole load.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE MACRO to_int(x) AS
    TRY_CAST(replace(NULLIF(trim(x), ''), ',', '') AS BIGINT);

-- month_of turns our 'YYYY-MM' filename label into the first-of-month DATE.
CREATE OR REPLACE MACRO month_of(label) AS
    strptime(label || '-01', '%Y-%m-%d')::DATE;

-- ----------------------------------------------------------------------------
-- typed : one CTE that casts every measure once and computes the month.
--         The national TOTAL row is identified case-insensitively and after
--         trimming, because the source spells it 'TOTAL', 'Total', 'Total '
--         inconsistently across months.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE TEMP VIEW v_typed AS
WITH typed AS (
    SELECT
        month_of(source_label)                       AS period_month,
        trim(org_code)                               AS org_code,
        trim(parent_org)                             AS region,
        trim(org_name)                               AS org_name,
        upper(trim(org_code)) = 'TOTAL'              AS is_total,
        to_int(att_type1)                            AS att_type1,
        -- all-types attendances = Type 1 + Type 2 + Other; COALESCE so a NULL
        -- component doesn't null the whole sum.
        COALESCE(to_int(att_type1), 0)
          + COALESCE(to_int(att_type2), 0)
          + COALESCE(to_int(att_other), 0)           AS att_all,
        to_int(over4hr_type1)                        AS over4hr_type1,
        COALESCE(to_int(over4hr_type1), 0)
          + COALESCE(to_int(over4hr_type2), 0)
          + COALESCE(to_int(over4hr_other), 0)       AS over4hr_all,
        to_int(waited_4_12hr_dta)                    AS waited_4_12hr_dta,
        to_int(waited_12hr_dta)                      AS waited_12hr_dta
    FROM stg_ae_raw
)
SELECT
    *,
    -- 4-hour performance = share of attendances seen within 4 hours.
    -- Guard the denominator: NULL (not divide-by-zero) when attendances = 0,
    -- e.g. a site reporting only booked/other activity in a given month.
    CASE WHEN att_all   > 0 THEN 1.0 - over4hr_all   / att_all::DOUBLE   END AS perf_all,
    CASE WHEN att_type1 > 0 THEN 1.0 - over4hr_type1 / att_type1::DOUBLE END AS perf_type1
FROM typed;

-- ----------------------------------------------------------------------------
-- Provider table: everything that is NOT the national total.
-- ----------------------------------------------------------------------------
INSERT INTO ae_provider
SELECT
    period_month, org_code, region, org_name,
    att_type1, att_all, over4hr_type1, over4hr_all,
    waited_4_12hr_dta, waited_12hr_dta, perf_all, perf_type1
FROM v_typed
WHERE NOT is_total;

-- ----------------------------------------------------------------------------
-- National table: the single TOTAL row per month.
-- ----------------------------------------------------------------------------
INSERT INTO ae_national
SELECT
    period_month,
    att_type1, att_all, over4hr_type1, over4hr_all,
    waited_4_12hr_dta, waited_12hr_dta, perf_all, perf_type1
FROM v_typed
WHERE is_total;
