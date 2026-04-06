"""
Download real air quality data from quotsoft.net/air/ (CNEMC archive)
and aggregate to monthly city-level averages for GBA cities.

Data source: Wang Xiaolei's CNEMC archive (https://quotsoft.net/air/)
Original data: China National Environmental Monitoring Centre (中国环境监测总站)
"""

import os
import io
import sys
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

# GBA cities (column names in the CSV)
GBA_CITIES = {
    '广州': ('Guangzhou', 23.13, 113.26),
    '深圳': ('Shenzhen', 22.54, 114.06),
    '珠海': ('Zhuhai', 22.27, 113.58),
    '佛山': ('Foshan', 23.02, 113.12),
    '惠州': ('Huizhou', 23.11, 114.42),
    '东莞': ('Dongguan', 23.02, 113.75),
    '中山': ('Zhongshan', 22.52, 113.38),
    '江门': ('Jiangmen', 22.58, 113.08),
    '肇庆': ('Zhaoqing', 23.05, 112.47),
}

# Pollutant types to extract (use 24h averages where available)
POLLUTANT_TYPES = ['AQI', 'PM2.5', 'PM10', 'SO2', 'NO2', 'CO', 'O3']

BASE_URL = "https://quotsoft.net/air/data/china_cities_{}.csv"
START_DATE = datetime(2015, 1, 1)
END_DATE = datetime(2024, 12, 31)
SAMPLE_INTERVAL = 3  # download every N days


def generate_dates(start, end, interval):
    """Generate dates to download."""
    dates = []
    current = start
    while current <= end:
        dates.append(current)
        current += timedelta(days=interval)
    return dates


def download_one_day(date):
    """Download and parse one daily file, return GBA data or None."""
    date_str = date.strftime('%Y%m%d')
    url = BASE_URL.format(date_str)
    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (research project)'})
        with urlopen(req, timeout=15) as resp:
            raw = resp.read().decode('utf-8')

        df = pd.read_csv(io.StringIO(raw))

        # Keep only GBA city columns + metadata
        gba_cols = [c for c in GBA_CITIES.keys() if c in df.columns]
        if not gba_cols:
            return None

        meta_cols = ['date', 'hour', 'type']
        keep_cols = [c for c in meta_cols if c in df.columns] + gba_cols
        df = df[keep_cols]

        # Filter for target pollutant types
        df = df[df['type'].isin(POLLUTANT_TYPES)]

        # Convert city columns to numeric
        for c in gba_cols:
            df[c] = pd.to_numeric(df[c], errors='coerce')

        # Compute daily mean per city per pollutant (across hours)
        daily = df.groupby('type')[gba_cols].mean()

        # Reshape: one row per city
        records = []
        for city_zh in gba_cols:
            en_name, lat, lon = GBA_CITIES[city_zh]
            row = {
                'date': date.strftime('%Y-%m-%d'),
                'year_month': date.strftime('%Y-%m'),
                'city': en_name,
                'city_zh': city_zh,
                'lat': lat,
                'lon': lon,
            }
            for p in POLLUTANT_TYPES:
                if p in daily.index:
                    row[p] = round(daily.loc[p, city_zh], 2) if not pd.isna(daily.loc[p, city_zh]) else np.nan
                else:
                    row[p] = np.nan
            records.append(row)

        return records

    except (HTTPError, URLError, Exception) as e:
        return None


def main():
    dates = generate_dates(START_DATE, END_DATE, SAMPLE_INTERVAL)
    print(f"Downloading {len(dates)} daily files ({START_DATE.strftime('%Y-%m-%d')} to "
          f"{END_DATE.strftime('%Y-%m-%d')}, every {SAMPLE_INTERVAL} days)...")

    all_records = []
    failed = 0
    done = 0

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(download_one_day, d): d for d in dates}

        for future in as_completed(futures):
            done += 1
            result = future.result()
            if result:
                all_records.extend(result)
            else:
                failed += 1

            if done % 50 == 0 or done == len(dates):
                print(f"  Progress: {done}/{len(dates)} files "
                      f"({len(all_records)} records, {failed} failed)")

    if not all_records:
        print("ERROR: No data downloaded. Check internet connection.")
        sys.exit(1)

    # Build daily DataFrame
    daily_df = pd.DataFrame(all_records)
    print(f"\nDaily data: {len(daily_df)} records")

    # Aggregate to monthly means
    monthly = daily_df.groupby(['year_month', 'city', 'city_zh', 'lat', 'lon'])[
        POLLUTANT_TYPES
    ].mean().round(1).reset_index()
    monthly.rename(columns={'year_month': 'date'}, inplace=True)

    # Sort
    monthly = monthly.sort_values(['date', 'city']).reset_index(drop=True)

    # Save
    out_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'gba_air_quality_2015_2024.csv')
    monthly.to_csv(out_path, index=False)
    print(f"\nSaved {len(monthly)} monthly records to {out_path}")
    print(f"\nSample:")
    print(monthly.head(9).to_string(index=False))
    print(f"\nPM2.5 by city (full period mean):")
    print(monthly.groupby('city')['PM2.5'].mean().round(1).sort_values().to_string())


if __name__ == '__main__':
    main()
