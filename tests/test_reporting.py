import duckdb
import pandas as pd
import pytest

from nhs_ae.reporting import comparison, connect_snapshot, monthly, period_summary


def connection(frame):
    con = duckdb.connect(":memory:")
    con.register("frame", frame)
    con.sql("CREATE TABLE ae_provider AS SELECT * FROM frame")
    return con


def data():
    dates = pd.date_range("2024-04-01", periods=24, freq="MS")
    return pd.DataFrame(
        {
            "period_month": dates,
            "org_code": "ABC",
            "org_name": "Example",
            "region": "Region",
            "att_type1": 100,
            "over4hr_type1": 20,
            "waited_12hr_dta": 0,
        }
    )


def test_rolling_is_weighted_and_needs_three_months():
    d = data().iloc[:3].copy()
    d.loc[0, ["att_type1", "over4hr_type1"]] = [1000, 500]
    with connection(d) as con:
        m = monthly(con, "ABC")
    assert m.rolling_3m_pct.iloc[:2].isna().all()
    assert m.rolling_3m_pct.iloc[2] == pytest.approx(55)
    assert m.rolling_3m_pct.iloc[2] != pytest.approx(m.within_4h_pct.mean())


def test_missing_month_does_not_shift_yoy_or_rolling():
    d = data().drop(index=1)
    with connection(d) as con:
        m = monthly(con, "ABC")
    assert m.loc[m.period_month == "2025-05-01", "yoy_pp"].isna().all()
    assert m.loc[m.period_month == "2024-06-01", "rolling_3m_pct"].isna().all()


def test_partial_year_excluded_even_with_high_volume():
    d = data().drop(index=1)
    d["att_type1"] = 100000
    with connection(d) as con:
        assert comparison(con, 0).empty


def test_comparison_uses_complete_weighted_years_and_latest_name():
    d = data()
    d.loc[12:, "over4hr_type1"] = 10
    d.loc[23, "org_name"] = "New name"
    with connection(d) as con:
        r = comparison(con, 1000).iloc[0]
    assert r.perf_prior_pct == 80
    assert r.perf_latest_pct == 90
    assert r.recovery_pp == 10
    assert r.org_name == "New name"
    assert r.names_in_window == 2


def test_zero_volume_has_no_rate():
    assert period_summary(pd.DataFrame({"attendances": [0], "over_4h": [0]}))["performance"] is None


def test_real_snapshot_totals_and_coverage():
    with connect_snapshot() as con:
        assert con.sql("SELECT count(*) FROM ae_provider").fetchone()[0] == 4758
        diffs = con.sql("""SELECT p.period_month FROM ae_provider p JOIN ae_national n USING(period_month)
            GROUP BY p.period_month,n.att_all,n.over4hr_all
            HAVING SUM(p.att_all)<>n.att_all OR SUM(p.over4hr_all)<>n.over4hr_all""").df()
        assert diffs.empty
        assert con.sql("SELECT count(*) FROM ae_national").fetchone()[0] == 24
        provider = con.sql(
            "SELECT org_code FROM ae_provider GROUP BY org_code HAVING count(*)=24 ORDER BY org_code LIMIT 1"
        ).fetchone()[0]
        assert monthly(con, provider).shape[0] == 24


def test_unsupported_department_rejected():
    with connect_snapshot() as con, pytest.raises(ValueError):
        monthly(con, department="invented")
