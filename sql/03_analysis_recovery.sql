-- Descriptive same-provider comparison, not causal recovery or a league table of quality.
-- Require 12 months of positive Type 1 activity in EACH window. Organisation codes
-- remain imperfect longitudinal identifiers: name changes and reorganisations need review.
WITH anchor AS (SELECT max(period_month) AS latest FROM ae_provider),
windowed AS (
    SELECT p.*, CASE WHEN period_month > latest - INTERVAL 12 MONTH
        THEN 'latest' ELSE 'prior' END AS window_name
    FROM ae_provider p CROSS JOIN anchor
    WHERE period_month > latest - INTERVAL 24 MONTH AND att_type1 > 0
),
aggregated AS (
    SELECT org_code, arg_max(org_name,period_month) AS org_name,
        arg_max(region,period_month) AS region,
        count(DISTINCT org_name) AS names_in_window,
        count(*) FILTER (WHERE window_name='latest') AS months_latest,
        count(*) FILTER (WHERE window_name='prior') AS months_prior,
        sum(att_type1) FILTER (WHERE window_name='latest') AS att_latest,
        sum(att_type1) FILTER (WHERE window_name='prior') AS att_prior,
        100.0*(1-sum(over4hr_type1) FILTER (WHERE window_name='latest') /
            nullif(sum(att_type1) FILTER (WHERE window_name='latest'),0)) AS perf_latest_pct,
        100.0*(1-sum(over4hr_type1) FILTER (WHERE window_name='prior') /
            nullif(sum(att_type1) FILTER (WHERE window_name='prior'),0)) AS perf_prior_pct
    FROM windowed GROUP BY org_code
),
changes AS (
    SELECT *, perf_latest_pct-perf_prior_pct AS recovery_pp
    FROM aggregated WHERE months_latest=12 AND months_prior=12
      AND least(att_latest,att_prior) >= ?
)
SELECT *, rank() OVER (ORDER BY recovery_pp DESC) AS recovery_rank
FROM changes ORDER BY recovery_pp DESC, org_code;
