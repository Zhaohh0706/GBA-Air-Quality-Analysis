"""The analyses the README reports, as functions over the committed tables.

Each one answers a single question and returns a table, so the figures and the
README quote the same numbers. Nothing here reads the raw archive.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import metrics

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# The annual assessment statistic for each pollutant, in the order reported.
ASSESSED = ["PM2.5", "PM10", "NO2", "SO2", "O3_MDA8_P90", "CO_P95"]

LABEL = {"PM2.5": "PM2.5", "PM10": "PM10", "NO2": "NO2", "SO2": "SO2",
         "O3_MDA8_P90": "O3 (MDA8, 90th pct)", "CO_P95": "CO (95th pct)",
         "O3_MDA8": "O3 (MDA8)", "CO": "CO"}

# Spring Festival (正月初一), which empties Guangdong's factories for a
# fortnight every year and lands anywhere from late January to mid February. A
# February comparison that ignores it is partly measuring the calendar.
SPRING_FESTIVAL = {2017: "2017-01-28", 2018: "2018-02-16", 2019: "2019-02-05",
                   2020: "2020-01-25"}


def load() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    days = pd.read_csv(DATA / "gba_daily_2015_2024.csv", parse_dates=["date"])
    months = pd.read_csv(DATA / "gba_monthly_2015_2024.csv")
    years = pd.read_csv(DATA / "gba_annual_2015_2024.csv")
    return days, months, years


def regional(years: pd.DataFrame) -> pd.DataFrame:
    """The nine-city mean per year, only where all nine cities are valid.

    A regional mean over whichever cities happen to have data in a given year
    moves when the membership moves, and that movement looks like a trend.
    """
    rows = []
    for year, group in years.groupby("year"):
        row = {"year": year}
        for p in ASSESSED:
            values = group[p]
            row[p] = values.mean() if values.notna().sum() == len(metrics.CITIES) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def trends(years: pd.DataFrame) -> pd.DataFrame:
    """Theil–Sen trend and Mann–Kendall p for every city and pollutant, plus the region."""
    rows = []
    for city, group in years.groupby("city"):
        for p in ASSESSED:
            rows.append({"city": city, "pollutant": p, **metrics.trend(group["year"], group[p])})
    region = regional(years)
    for p in ASSESSED:
        rows.append({"city": "GBA (9-city mean)", "pollutant": p,
                     **metrics.trend(region["year"], region[p])})
    return pd.DataFrame(rows)


def seasonal_cycle(months: pd.DataFrame) -> pd.DataFrame:
    """Mean by calendar month across all years and cities."""
    frame = months.assign(calendar_month=pd.PeriodIndex(months["month"], freq="M").month)
    return frame.groupby("calendar_month")[[*metrics.DAILY_MEAN, "O3_MDA8"]].mean()


def lockdown_february(days: pd.DataFrame) -> pd.DataFrame:
    """February 2020 against the mean of February 2017–2019, region-wide.

    Guangdong's first-level emergency response ran from 23 January to 24
    February 2020, so February is the month inside it. The baseline is the same
    month in the three preceding years rather than January 2020, because the
    seasonal swing from January to February is itself larger than some of the
    effects being looked for.
    """
    feb = days[days["date"].dt.month == 2]
    by_year = feb.groupby(feb["date"].dt.year)[[*metrics.DAILY_MEAN, "O3_MDA8"]].mean()
    base = by_year.loc[[2017, 2018, 2019]].mean()
    spread = by_year.loc[[2017, 2018, 2019]].std()
    covid = by_year.loc[2020]
    return pd.DataFrame({
        "feb_2017_2019": base, "feb_2017_2019_sd": spread, "feb_2020": covid,
        "change_pct": 100.0 * (covid - base) / base,
    })


def lockdown_holiday_aligned(days: pd.DataFrame, start: int = 8, length: int = 30) -> pd.DataFrame:
    """The lockdown effect with the Spring Festival held fixed.

    Every year, factories empty for the holiday and refill over the following
    weeks. Comparing February 2020 with earlier Februaries therefore mixes the
    lockdown with where the holiday fell. Aligning on the holiday instead — days
    ``start`` to ``start + length`` after 正月初一 in each year — puts the
    holiday dip in every window, so what differs in 2020 is that the return to
    work did not happen. The first week after the festival is skipped because
    it is holiday in every year alike.
    """
    pollutants = [*metrics.DAILY_MEAN, "O3_MDA8"]
    windows = {}
    for year, festival in SPRING_FESTIVAL.items():
        first = pd.Timestamp(festival) + pd.Timedelta(days=start)
        last = first + pd.Timedelta(days=length)
        window = days[(days["date"] >= first) & (days["date"] < last)]
        windows[year] = window[pollutants].mean()
    table = pd.DataFrame(windows).T
    base = table.loc[[2017, 2018, 2019]].mean()
    return pd.DataFrame({
        "aligned_2017_2019": base,
        "aligned_2017_2019_sd": table.loc[[2017, 2018, 2019]].std(),
        "aligned_2020": table.loc[2020],
        "change_pct": 100.0 * (table.loc[2020] - base) / base,
    })


def against_standard(years: pd.DataFrame, year: int) -> pd.DataFrame:
    """Each city's assessed values in ``year`` as a share of the Grade II limit."""
    group = years[years["year"] == year].set_index("city")
    out = pd.DataFrame(index=group.index)
    for p, limit in metrics.GRADE_II.items():
        out[p] = 100.0 * group[p] / limit
    return out.sort_values("PM2.5")
