-- ============================================================================
-- 01_schema.sql — table definitions for the NHS A&E analytics database
-- ============================================================================
-- Strict Python validation precedes this staging -> typed split. The canonical
-- source columns are retained as text after whitespace/count normalization.
-- Unknown populated columns, missing counts and duplicate keys fail the build;
-- no rows are skipped or silently deduplicated. Empty surplus CSV columns are
-- explicitly checked and recorded in reports/quality.json.
--
-- source_label comes from the pinned manifest month. Provider Period values
-- must match it. The national TOTAL row does not carry a reporting date.
-- The typed tables are built in a temporary database and published only after
-- all six reporting measures reconcile with the national total every month.
-- ============================================================================

-- Fresh build every run so the pipeline is deterministic and idempotent.
DROP TABLE IF EXISTS stg_ae_raw;
DROP TABLE IF EXISTS ae_provider;
DROP TABLE IF EXISTS ae_national;

-- ----------------------------------------------------------------------------
-- Staging: raw text, one row per (file, CSV row). Column names mirror the
-- source header but are snake_cased. Everything is VARCHAR at this stage.
-- ----------------------------------------------------------------------------
CREATE TABLE stg_ae_raw (
    source_label            VARCHAR,   -- YYYY-MM, injected from filename
    period_raw              VARCHAR,   -- e.g. 'MSitAE-MARCH-2026' (or 'TOTAL' on the total row)
    org_code                VARCHAR,
    parent_org              VARCHAR,   -- NHS England region (has trailing spaces in source)
    org_name                VARCHAR,
    att_type1               VARCHAR,
    att_type2               VARCHAR,
    att_other               VARCHAR,
    att_booked_type1        VARCHAR,
    att_booked_type2        VARCHAR,
    att_booked_other        VARCHAR,
    over4hr_type1           VARCHAR,
    over4hr_type2           VARCHAR,
    over4hr_other           VARCHAR,
    over4hr_booked_type1    VARCHAR,
    over4hr_booked_type2    VARCHAR,
    over4hr_booked_other    VARCHAR,
    waited_4_12hr_dta       VARCHAR,   -- 4-12h from Decision-To-Admit to admission
    waited_12hr_dta         VARCHAR,   -- 12h+ from DTA to admission
    emadm_type1             VARCHAR,   -- emergency admissions via A&E, Type 1
    emadm_type2             VARCHAR,
    emadm_other             VARCHAR,
    emadm_other_emergency   VARCHAR
);

-- ----------------------------------------------------------------------------
-- Clean provider-level table: typed integers, real month DATE, derived
-- 4-hour performance metrics. Excludes the national TOTAL row.
-- Natural key = (period_month, org_code).
-- ----------------------------------------------------------------------------
CREATE TABLE ae_provider (
    period_month        DATE     NOT NULL,  -- first day of the reporting month
    org_code            VARCHAR  NOT NULL,
    region              VARCHAR,            -- trimmed parent_org
    org_name            VARCHAR,
    -- attendances
    att_type1           BIGINT,
    att_all             BIGINT,             -- Type 1 + Type 2 + Other
    -- attendances breaching the 4-hour standard
    over4hr_type1       BIGINT,
    over4hr_all         BIGINT,
    -- long DTA waits (trolley waits)
    waited_4_12hr_dta   BIGINT,
    waited_12hr_dta     BIGINT,
    -- derived 4-hour performance = 1 - (breaches / attendances), in [0,1]
    perf_all            DOUBLE,             -- all A&E types
    perf_type1          DOUBLE,             -- Type 1 (major) A&E only
    PRIMARY KEY (period_month, org_code)
);

-- ----------------------------------------------------------------------------
-- Clean national table: the single TOTAL row per month, England-wide.
-- Used as the national time series for the seasonality analysis.
-- ----------------------------------------------------------------------------
CREATE TABLE ae_national (
    period_month        DATE     NOT NULL PRIMARY KEY,
    att_type1           BIGINT,
    att_all             BIGINT,
    over4hr_type1       BIGINT,
    over4hr_all         BIGINT,
    waited_4_12hr_dta   BIGINT,
    waited_12hr_dta     BIGINT,
    perf_all            DOUBLE,
    perf_type1          DOUBLE
);
