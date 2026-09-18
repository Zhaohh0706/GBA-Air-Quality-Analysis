"""Download city-level air quality for the nine Greater Bay Area cities, 2015–2024.

Source: the China National Environmental Monitoring Centre's real-time national
city air quality platform, as archived day by day at https://quotsoft.net/air/
(maintained by Wang Xiaolei, published "for analysis and research"). One file
per day, one row per hour and pollutant, one column per city.

Every day is fetched, not a sample of days. Monthly means computed from every
third day, which is what an earlier version of this repository did, carry a
sampling error that is invisible in the result.

Only the nine GBA columns are kept, and each day is cached as it arrives, so a
rerun asks the archive for nothing it has already sent.
"""
from __future__ import annotations

import io
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "raw_cache"  # not committed; see .gitignore

URL = "https://quotsoft.net/air/data/china_cities_{:%Y%m%d}.csv"
USER_AGENT = "gba-air-quality-analysis (research; one request per day-file)"

CITIES = ["广州", "深圳", "珠海", "佛山", "惠州", "东莞", "中山", "江门", "肇庆"]
# Hourly concentrations, plus the running 8-hour ozone mean that the daily ozone
# metric in GB 3095-2012 is built from.
TYPES = ["PM2.5", "PM10", "SO2", "NO2", "CO", "O3", "O3_8h", "AQI"]

START, END = date(2015, 1, 1), date(2024, 12, 31)


def fetch(day: date, retries: int = 4) -> str:
    """Cache one day's GBA rows. Returns 'cached', 'ok', 'missing' or 'failed'."""
    target = CACHE / f"{day:%Y%m%d}.parquet"
    if target.exists():
        return "cached"
    request = urllib.request.Request(URL.format(day), headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read().decode("utf-8", errors="replace")
            frame = pd.read_csv(io.StringIO(raw))
            keep = [c for c in CITIES if c in frame.columns]
            frame = frame.loc[frame["type"].isin(TYPES), ["date", "hour", "type", *keep]]
            frame.to_parquet(target, index=False)
            return "ok"
        except urllib.error.HTTPError as error:
            if error.code == 404:
                # The archive says some days are missing at source.  Recorded
                # as missing, not retried and not filled.
                (CACHE / f"{day:%Y%m%d}.missing").touch()
                return "missing"
        except Exception:  # noqa: BLE001 - network, retried
            pass
        time.sleep(2 * (attempt + 1))
    return "failed"


def main(workers: int = 4) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    days = [START + timedelta(n) for n in range((END - START).days + 1)]
    todo = [d for d in days if not (CACHE / f"{d:%Y%m%d}.parquet").exists()
            and not (CACHE / f"{d:%Y%m%d}.missing").exists()]
    print(f"{len(days)} days in range, {len(days) - len(todo)} already cached, "
          f"{len(todo)} to fetch", flush=True)

    counts: dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch, d): d for d in todo}
        for n, future in enumerate(as_completed(futures), 1):
            status = future.result()
            counts[status] = counts.get(status, 0) + 1
            if n % 250 == 0 or n == len(todo):
                print(f"  {n}/{len(todo)} {counts}", flush=True)
    if counts.get("failed"):
        print(f"{counts['failed']} days failed; rerun to retry them", file=sys.stderr)


if __name__ == "__main__":
    main()
