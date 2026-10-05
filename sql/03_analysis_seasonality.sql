-- Two winters support description only, not a structural-versus-seasonal diagnosis.
-- Weighted three-calendar-month percentages; first two months intentionally null.
SELECT period_month, 100*perf_all AS perf_all_pct, 100*perf_type1 AS perf_type1_pct,
    CASE WHEN count(*) OVER w=3 THEN
       100*(1-sum(over4hr_all) OVER w/nullif(sum(att_all) OVER w,0)) END AS perf_all_roll3_pct,
    month(period_month) IN (12,1,2) AS is_winter
FROM ae_national
WINDOW w AS (ORDER BY period_month RANGE BETWEEN INTERVAL 2 MONTH PRECEDING AND CURRENT ROW)
ORDER BY period_month;
