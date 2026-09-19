"""Tests for the validity rules and the statistics built on them.

Each rule is tested at its boundary, because that is where an off-by-one turns a
missing value into an estimate without anyone noticing.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gba import metrics as m


def _hourly(day: str, city_values: dict[str, list[float]], kind: str = "PM2.5") -> pd.DataFrame:
    rows = []
    hours = len(next(iter(city_values.values())))
    for h in range(hours):
        row = {"date": int(day), "hour": h, "type": kind}
        for city, values in city_values.items():
            row[city] = values[h]
        rows.append(row)
    return pd.DataFrame(rows)


class TestDailyMean:
    def test_twenty_hours_is_enough(self):
        values = [10.0] * 20 + [np.nan] * 4
        out = m.daily(_hourly("20200101", {"深圳": values}))
        assert out.loc[0, "PM2.5"] == pytest.approx(10.0)

    def test_nineteen_hours_is_not(self):
        values = [10.0] * 19 + [np.nan] * 5
        out = m.daily(_hourly("20200101", {"深圳": values}))
        assert np.isnan(out.loc[0, "PM2.5"])

    def test_cities_are_named_in_english_as_well(self):
        out = m.daily(_hourly("20200101", {"深圳": [10.0] * 24}))
        assert out.loc[0, "city"] == "Shenzhen"


class TestMDA8:
    def _o3(self, values):
        return _hourly("20200701", {"广州": values}, kind="O3_8h")

    def test_the_daily_maximum_is_taken_over_the_afternoon_window(self):
        values = [50.0] * 24
        values[3] = 999.0   # before 08:00: outside the window
        values[15] = 180.0  # inside it
        out = m.daily(self._o3(values))
        assert out.loc[0, "O3_MDA8"] == pytest.approx(180.0)

    def test_fourteen_values_in_the_window_is_enough(self):
        values = [np.nan] * 8 + [60.0] * 14 + [np.nan] * 2
        assert m.daily(self._o3(values)).loc[0, "O3_MDA8"] == pytest.approx(60.0)

    def test_thirteen_is_not(self):
        values = [np.nan] * 8 + [60.0] * 13 + [np.nan] * 3
        assert np.isnan(m.daily(self._o3(values)).loc[0, "O3_MDA8"])


def _days(city: str, dates: pd.DatetimeIndex, value: float = 30.0) -> pd.DataFrame:
    frame = pd.DataFrame({"date": dates, "city": city, "city_zh": "深圳"})
    for p in [*m.DAILY_MEAN, "O3_MDA8"]:
        frame[p] = value
    return frame


class TestMonthly:
    def test_twenty_seven_days_is_a_valid_month(self):
        days = _days("Shenzhen", pd.date_range("2020-01-01", periods=27))
        assert m.monthly(days).loc[0, "PM2.5"] == pytest.approx(30.0)

    def test_twenty_six_is_not(self):
        days = _days("Shenzhen", pd.date_range("2020-01-01", periods=26))
        assert np.isnan(m.monthly(days).loc[0, "PM2.5"])

    def test_february_needs_only_twenty_five(self):
        days = _days("Shenzhen", pd.date_range("2021-02-01", periods=25))
        assert m.monthly(days).loc[0, "PM2.5"] == pytest.approx(30.0)


class TestAnnual:
    def test_ozone_is_assessed_on_the_90th_percentile_not_the_mean(self):
        dates = pd.date_range("2020-01-01", "2020-12-31")
        days = _days("Shenzhen", dates)
        days["O3_MDA8"] = np.linspace(0, 200, len(dates))
        out = m.annual(days)
        assert out.loc[0, "O3_MDA8_P90"] == pytest.approx(180.0, abs=1.0)

    def test_a_year_short_of_324_days_is_missing(self):
        days = _days("Shenzhen", pd.date_range("2020-01-01", periods=323))
        out = m.annual(days)
        assert np.isnan(out.loc[0, "PM2.5"])


class TestTrend:
    def test_a_single_outlier_year_does_not_move_theil_sen(self):
        years = pd.Series(range(2015, 2025))
        clean = pd.Series([40.0 - 2 * i for i in range(10)])
        spiked = clean.copy()
        spiked.iloc[5] = 90.0
        assert m.trend(years, spiked)["slope"] == pytest.approx(m.trend(years, clean)["slope"], abs=0.3)

    def test_a_steady_decline_is_significant(self):
        years = pd.Series(range(2015, 2025))
        values = pd.Series([40.0 - 2 * i for i in range(10)])
        out = m.trend(years, values)
        assert out["slope"] == pytest.approx(-2.0)
        assert out["p"] < 0.001
        assert out["change_pct"] == pytest.approx(-45.0)

    def test_too_few_years_returns_nothing_rather_than_a_slope(self):
        out = m.trend(pd.Series([2015, 2016, 2017]), pd.Series([1.0, 2.0, 3.0]))
        assert np.isnan(out["slope"])


class TestRegional:
    def test_a_year_missing_a_city_has_no_regional_mean(self):
        from gba import analysis
        rows = []
        for i, (zh, en) in enumerate(m.CITIES.items()):
            for year in (2020, 2021):
                value = np.nan if (year == 2021 and en == "Zhuhai") else 30.0
                rows.append({"city": en, "year": year, **{p: value for p in analysis.ASSESSED}})
        out = analysis.regional(pd.DataFrame(rows)).set_index("year")
        assert out.loc[2020, "PM2.5"] == pytest.approx(30.0)
        # Averaging the eight that remain would move the mean with the
        # membership, and that movement would read as a trend.
        assert np.isnan(out.loc[2021, "PM2.5"])


class TestStandard:
    def test_ozone_is_compared_on_its_assessment_statistic(self):
        assert m.GRADE_II["O3_MDA8_P90"] == 160.0
        assert "O3_MDA8" not in m.GRADE_II  # no annual-mean limit exists

    def test_co_is_assessed_on_the_95th_percentile(self):
        dates = pd.date_range("2020-01-01", "2020-12-31")
        days = _days("Shenzhen", dates)
        days["CO"] = np.linspace(0, 2, len(dates))
        assert m.annual(days).loc[0, "CO_P95"] == pytest.approx(1.9, abs=0.01)


class TestLockdown:
    def _days(self, bump_2020: float) -> pd.DataFrame:
        # A constant 40 everywhere, dropping to 20 in the 30 days after each
        # Spring Festival's first week, with an extra drop in 2020.
        from gba import analysis
        dates = pd.date_range("2017-01-01", "2020-12-31")
        values = np.full(len(dates), 40.0)
        for year, festival in analysis.SPRING_FESTIVAL.items():
            first = pd.Timestamp(festival) + pd.Timedelta(days=8)
            window = (dates >= first) & (dates < first + pd.Timedelta(days=30))
            values[window] = 20.0 - (bump_2020 if year == 2020 else 0.0)
        frame = pd.DataFrame({"date": dates, "city": "Shenzhen", "city_zh": "深圳"})
        for p in [*m.DAILY_MEAN, "O3_MDA8"]:
            frame[p] = values
        return frame

    def test_the_holiday_alone_produces_no_aligned_effect(self):
        from gba import analysis
        out = analysis.lockdown_holiday_aligned(self._days(bump_2020=0.0))
        assert out.loc["PM2.5", "change_pct"] == pytest.approx(0.0)

    def test_an_extra_2020_drop_is_recovered(self):
        from gba import analysis
        out = analysis.lockdown_holiday_aligned(self._days(bump_2020=5.0))
        assert out.loc["PM2.5", "change_pct"] == pytest.approx(-25.0)

    def test_a_calendar_february_comparison_is_confounded_by_the_holiday(self):
        # With no lockdown effect at all, February 2020 still differs from
        # earlier Februaries purely because the holiday fell elsewhere.
        from gba import analysis
        out = analysis.lockdown_february(self._days(bump_2020=0.0))
        assert abs(out.loc["PM2.5", "change_pct"]) > 5.0


class TestAQI:
    """HJ 633-2012 Table 1, checked at its breakpoints."""

    @pytest.mark.parametrize("pollutant,concentration,expected", [
        ("PM2.5", 35, 50), ("PM2.5", 75, 100), ("PM2.5", 115, 150),
        ("O3_MDA8", 100, 50), ("O3_MDA8", 160, 100), ("O3_MDA8", 215, 150),
        ("NO2", 40, 50), ("PM10", 150, 100), ("CO", 4, 100), ("SO2", 150, 100),
    ])
    def test_breakpoints_map_exactly(self, pollutant, concentration, expected):
        from gba import aqi
        assert aqi.iaqi(pollutant, concentration) == expected

    def test_sub_indices_are_rounded_up_not_to_nearest(self):
        # PM2.5 36 µg/m³ interpolates to 51.25; the standard rounds up, to 52.
        from gba import aqi
        assert aqi.iaqi("PM2.5", 36) == 52

    def test_ties_make_both_pollutants_primary(self):
        from gba import aqi
        day = pd.DataFrame([{"date": pd.Timestamp("2020-07-01"), "city": "Shenzhen",
                             "PM2.5": 75.0, "O3_MDA8": 160.0, "PM10": 10.0,
                             "NO2": 10.0, "SO2": 5.0, "CO": 0.5}])
        out = aqi.daily(day).iloc[0]
        assert out["AQI"] == 100
        assert out["primary_PM2.5"] and out["primary_O3_MDA8"]

    def test_no_primary_pollutant_at_or_below_fifty(self):
        from gba import aqi
        day = pd.DataFrame([{"date": pd.Timestamp("2020-07-01"), "city": "Shenzhen",
                             "PM2.5": 30.0, "O3_MDA8": 90.0, "PM10": 40.0,
                             "NO2": 30.0, "SO2": 5.0, "CO": 0.5}])
        out = aqi.daily(day).iloc[0]
        assert out["AQI"] <= 50
        assert not any(out[f"primary_{p}"] for p in aqi.POLLUTANTS)

    def test_a_day_missing_any_pollutant_gets_no_aqi(self):
        from gba import aqi
        day = pd.DataFrame([{"date": pd.Timestamp("2020-07-01"), "city": "Shenzhen",
                             "PM2.5": 80.0, "O3_MDA8": np.nan, "PM10": 40.0,
                             "NO2": 30.0, "SO2": 5.0, "CO": 0.5}])
        assert aqi.daily(day).empty
