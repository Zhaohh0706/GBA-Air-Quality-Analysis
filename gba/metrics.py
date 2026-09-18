"""Daily, monthly and annual air quality metrics, by the Chinese standard's rules.

Averaging whatever hours happen to be present is the easy thing and the wrong
one: a day with four hours of data reported as a daily mean is a guess about the
other twenty. GB 3095-2012 says how many values a mean needs before it counts,
and HJ 663-2013 says which statistic an annual ozone assessment uses. Both are
followed here, and a value that does not meet the rule is missing rather than
estimated.

Units are those of the source: µg/m³ for every pollutant except CO, which is
mg/m³.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

CITIES = {
    "广州": "Guangzhou", "深圳": "Shenzhen", "珠海": "Zhuhai",
    "佛山": "Foshan", "惠州": "Huizhou", "东莞": "Dongguan",
    "中山": "Zhongshan", "江门": "Jiangmen", "肇庆": "Zhaoqing",
}

# Pollutants whose daily value is the mean of hourly concentrations.
DAILY_MEAN = ["PM2.5", "PM10", "SO2", "NO2", "CO"]

UNITS = {"PM2.5": "µg/m³", "PM10": "µg/m³", "SO2": "µg/m³", "NO2": "µg/m³",
         "CO": "mg/m³", "O3_MDA8": "µg/m³", "O3_MDA8_P90": "µg/m³", "CO_P95": "mg/m³"}

# GB 3095-2012 Grade II limits, the ones that apply to cities, in the form each
# pollutant's annual assessment uses (HJ 663-2013): annual means for four of
# them, the 90th percentile of daily MDA8 for ozone, the 95th percentile of
# daily means for CO.
GRADE_II = {"PM2.5": 35.0, "PM10": 70.0, "SO2": 60.0, "NO2": 40.0,
            "O3_MDA8_P90": 160.0, "CO_P95": 4.0}

# GB 3095-2012, table 4: minimum data for a valid mean.
MIN_HOURS_PER_DAY = 20
MIN_DAYS_PER_MONTH = 27
MIN_DAYS_PER_FEBRUARY = 25
MIN_DAYS_PER_YEAR = 324

# Ozone's daily metric is the maximum 8-hour running mean.  HJ 663-2013 takes it
# over the 8-hour means ending between 08:00 and 24:00 and requires 14 of them;
# the source's hours run 0–23, so the window here is 08–23 (16 values) and the
# requirement stays at 14.
MDA8_HOURS = range(8, 24)
MIN_MDA8_VALUES = 14


def daily(hourly: pd.DataFrame) -> pd.DataFrame:
    """One row per city and day, from the archive's hourly long table.

    ``hourly`` has columns date (YYYYMMDD), hour, type and one column per city
    in Chinese. Returns date, city, one column per pollutant and O3_MDA8, with
    NaN wherever the day fails its validity rule.
    """
    cities = [c for c in CITIES if c in hourly.columns]
    long = hourly.melt(
        id_vars=["date", "hour", "type"], value_vars=cities,
        var_name="city_zh", value_name="value",
    )
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    long = long.dropna(subset=["value"])

    keys = ["date", "city_zh"]
    empty = pd.MultiIndex.from_arrays([[], []], names=keys)

    means = long[long["type"].isin(DAILY_MEAN)]
    if means.empty:
        table = pd.DataFrame(index=empty, columns=DAILY_MEAN, dtype=float)
    else:
        grouped = means.groupby([*keys, "type"])["value"]
        table = grouped.mean().where(grouped.count() >= MIN_HOURS_PER_DAY).unstack("type")
    # A pollutant absent from a day is a missing column, not a missing day: keep
    # every column so downstream code never meets a KeyError on a quiet day.
    table = table.reindex(columns=DAILY_MEAN)

    ozone = long[(long["type"] == "O3_8h") & long["hour"].isin(MDA8_HOURS)]
    o3 = ozone.groupby(keys)["value"]
    mda8 = o3.max().where(o3.count() >= MIN_MDA8_VALUES).rename("O3_MDA8")
    # Outer join: a day with ozone and nothing else is still a day.
    table = table.join(mda8, how="outer")

    out = table.reset_index()
    out["date"] = pd.to_datetime(out["date"].astype(str), format="%Y%m%d")
    out["city"] = out["city_zh"].map(CITIES)
    return out[["date", "city", "city_zh", *DAILY_MEAN, "O3_MDA8"]]


def monthly(days: pd.DataFrame) -> pd.DataFrame:
    """Monthly means, missing where a month has too few valid days."""
    frame = days.assign(month=days["date"].dt.to_period("M"))
    pollutants = [*DAILY_MEAN, "O3_MDA8"]
    grouped = frame.groupby(["city", "month"])[pollutants]
    counts = grouped.count()
    required = pd.Series(
        [MIN_DAYS_PER_FEBRUARY if m.month == 2 else MIN_DAYS_PER_MONTH
         for m in counts.index.get_level_values("month")],
        index=counts.index,
    )
    return grouped.mean().where(counts.ge(required, axis=0)).reset_index()


def annual(days: pd.DataFrame) -> pd.DataFrame:
    """Annual assessment values per city.

    Concentration pollutants are annual means of daily values. Ozone is the 90th
    percentile of daily MDA8, the statistic HJ 663-2013 assesses against — an
    annual mean would dilute exactly the summer episodes the standard exists to
    catch.
    """
    frame = days.assign(year=days["date"].dt.year)
    grouped = frame.groupby(["city", "year"])
    means = grouped[DAILY_MEAN].mean().where(grouped[DAILY_MEAN].count() >= MIN_DAYS_PER_YEAR)
    o3 = grouped["O3_MDA8"]
    means["O3_MDA8_P90"] = o3.quantile(0.9).where(o3.count() >= MIN_DAYS_PER_YEAR)
    # CO likewise has no annual-mean limit; it is assessed on the 95th
    # percentile of daily means.
    co = grouped["CO"]
    means["CO_P95"] = co.quantile(0.95).where(co.count() >= MIN_DAYS_PER_YEAR)
    return means.reset_index()


def trend(years: pd.Series, values: pd.Series) -> dict:
    """Theil–Sen slope with a Mann–Kendall significance test.

    Ten annual values are too few for least squares to be trusted with one bad
    year in them. Theil–Sen is the median of pairwise slopes, so a single
    outlier year cannot drag it; Mann–Kendall asks only whether the ranks
    trend, which makes no assumption about the shape of the change.
    """
    keep = values.notna() & years.notna()
    x, y = years[keep].to_numpy(float), values[keep].to_numpy(float)
    if len(x) < 5:
        return {"n": int(len(x)), "slope": np.nan, "low": np.nan, "high": np.nan,
                "tau": np.nan, "p": np.nan, "change_pct": np.nan}
    slope, intercept, low, high = stats.theilslopes(y, x, alpha=0.95)
    tau, p = stats.kendalltau(x, y)
    start, end = intercept + slope * x.min(), intercept + slope * x.max()
    return {
        "n": int(len(x)), "slope": float(slope), "low": float(low), "high": float(high),
        "tau": float(tau), "p": float(p),
        # Change over the fitted line's span, which a single noisy end year
        # cannot distort the way a first-year-to-last-year ratio can.
        "change_pct": float(100.0 * (end - start) / start) if start else np.nan,
    }


def completeness(days: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """Share of calendar days with a valid daily value, per city and pollutant."""
    calendar = len(pd.date_range(start, end, freq="D"))
    pollutants = [*DAILY_MEAN, "O3_MDA8"]
    return (days.groupby("city")[pollutants].count() / calendar).round(3)
