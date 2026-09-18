"""Turn the cached hourly archive into the daily, monthly and annual tables.

Every table is built by the validity rules in ``gba.metrics``; nothing is
interpolated or filled. The days the archive does not have, and the days that
fail the rules, are written out rather than hidden, so a reader can see what the
annual figures stand on.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gba import metrics  # noqa: E402

CACHE = ROOT / "data" / "raw_cache"
DATA = ROOT / "data"
START, END = "2015-01-01", "2024-12-31"


def main() -> None:
    files = sorted(CACHE.glob("*.parquet"))
    missing = sorted(p.stem for p in CACHE.glob("*.missing"))
    if not files:
        raise SystemExit("no cached days; run scripts/download_cnemc.py first")

    hourly = pd.concat((pd.read_parquet(f) for f in files), ignore_index=True)
    days = metrics.daily(hourly).sort_values(["date", "city"]).reset_index(drop=True)
    days = days[(days["date"] >= START) & (days["date"] <= END)]

    rounded = {p: 2 if p == "CO" else 1 for p in [*metrics.DAILY_MEAN, "O3_MDA8"]}
    days.round(rounded).to_csv(DATA / "gba_daily_2015_2024.csv", index=False)

    months = metrics.monthly(days)
    months["month"] = months["month"].astype(str)
    months.round(rounded).to_csv(DATA / "gba_monthly_2015_2024.csv", index=False)

    years = metrics.annual(days)
    years.round({**rounded, "O3_MDA8_P90": 1}).to_csv(DATA / "gba_annual_2015_2024.csv", index=False)

    completeness = metrics.completeness(days, START, END)
    completeness.to_csv(DATA / "completeness.csv")

    calendar = pd.date_range(START, END, freq="D")
    (DATA / "missing_days.txt").write_text(
        "# Days absent from the archive (source-side gaps), YYYYMMDD\n"
        + "\n".join(missing) + "\n",
        encoding="utf-8",
    )

    print(f"{len(files)} archive days, {len(missing)} missing at source, "
          f"{len(calendar)} calendar days")
    print(f"daily rows {len(days):,} | monthly {len(months):,} | annual {len(years)}")
    print("\nshare of calendar days with a valid daily value:")
    print(completeness.to_string())


if __name__ == "__main__":
    main()
