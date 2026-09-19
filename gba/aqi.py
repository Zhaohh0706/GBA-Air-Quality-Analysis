"""Daily air quality index and primary pollutant, by HJ 633-2012.

The daily AQI is built from daily concentrations — 24-hour means, and ozone's
daily maximum 8-hour mean — not by averaging hourly AQI values, which is a
different quantity. Each pollutant's sub-index (IAQI) is interpolated between
the breakpoints of Table 1 and, as the standard requires, rounded **up** to an
integer (进位取整); the AQI is the largest IAQI, and when it exceeds 50 the
pollutant or pollutants that reach it are the primary pollutant.

A day's AQI is computed only when all six pollutants have a valid daily value.
Computing it from whichever pollutants happen to be present would let a missing
pollutant fail to be the primary one, and the shares would drift with data gaps.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

IAQI_LEVELS = [0, 50, 100, 150, 200, 300, 400, 500]

# HJ 633-2012 Table 1, daily-average breakpoints (µg/m³; CO in mg/m³). Ozone's
# 8-hour breakpoints stop at 800 (IAQI 300); above that the standard switches to
# the 1-hour value, which never happens in this record.
BREAKPOINTS = {
    "SO2": [0, 50, 150, 475, 800, 1600, 2100, 2620],
    "NO2": [0, 40, 80, 180, 280, 565, 750, 940],
    "PM10": [0, 50, 150, 250, 350, 420, 500, 600],
    "CO": [0, 2, 4, 14, 24, 36, 48, 60],
    "O3_MDA8": [0, 100, 160, 215, 265, 800],
    "PM2.5": [0, 35, 75, 115, 150, 250, 350, 500],
}
POLLUTANTS = list(BREAKPOINTS)


def iaqi(pollutant: str, concentration: float) -> float:
    """Sub-index for one pollutant; NaN when the concentration is missing."""
    if concentration is None or not np.isfinite(concentration) or concentration < 0:
        return np.nan
    points = BREAKPOINTS[pollutant]
    for i in range(len(points) - 1):
        low, high = points[i], points[i + 1]
        if low <= concentration <= high:
            value = (IAQI_LEVELS[i + 1] - IAQI_LEVELS[i]) / (high - low) * (concentration - low) + IAQI_LEVELS[i]
            return float(math.ceil(value - 1e-9))  # 进位取整; the epsilon keeps exact breakpoints exact
    return float(IAQI_LEVELS[len(points) - 1])  # above the table: capped at its top


def daily(days: pd.DataFrame) -> pd.DataFrame:
    """AQI and primary-pollutant flags for every city-day with all six pollutants valid."""
    valid = days.dropna(subset=POLLUTANTS).copy()
    scores = pd.DataFrame(
        {p: valid[p].map(lambda c, p=p: iaqi(p, c)) for p in POLLUTANTS}, index=valid.index
    )
    valid["AQI"] = scores.max(axis=1)
    polluted = valid["AQI"] > 50
    for p in POLLUTANTS:
        # Ties are shared: two pollutants at the maximum are both primary.
        valid[f"primary_{p}"] = polluted & scores[p].eq(valid["AQI"])
    return valid
