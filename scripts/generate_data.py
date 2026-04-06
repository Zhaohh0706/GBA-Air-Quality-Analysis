"""
Generate realistic synthetic monthly air quality data for 9 GBA cities (2015-2024).

Based on published trends from China's Ministry of Ecology and Environment annual reports
and Guangdong Provincial Environmental Monitoring Centre bulletins. The synthetic data
reproduces documented macro-trends (PM2.5 decline, O3 rise, COVID-19 dip) with realistic
city-level variation and seasonal patterns.

This script is provided for reproducibility. For production research, replace with
actual monitoring data from https://www.cnemc.cn/ or provincial data portals.
"""

import pandas as pd
import numpy as np

np.random.seed(42)

cities = {
    "Guangzhou":  {"lat": 23.13, "lon": 113.26, "pm25_2015": 40, "pm25_2024": 22, "urban": True},
    "Shenzhen":   {"lat": 22.54, "lon": 114.06, "pm25_2015": 30, "pm25_2024": 16, "urban": True},
    "Zhuhai":     {"lat": 22.27, "lon": 113.58, "pm25_2015": 28, "pm25_2024": 15, "urban": False},
    "Foshan":     {"lat": 23.02, "lon": 113.12, "pm25_2015": 45, "pm25_2024": 25, "urban": True},
    "Huizhou":    {"lat": 23.11, "lon": 114.42, "pm25_2015": 33, "pm25_2024": 19, "urban": False},
    "Dongguan":   {"lat": 23.02, "lon": 113.75, "pm25_2024": 20, "pm25_2015": 38, "urban": True},
    "Zhongshan":  {"lat": 22.52, "lon": 113.38, "pm25_2015": 35, "pm25_2024": 19, "urban": False},
    "Jiangmen":   {"lat": 22.58, "lon": 113.08, "pm25_2015": 36, "pm25_2024": 20, "urban": False},
    "Zhaoqing":   {"lat": 23.05, "lon": 112.47, "pm25_2015": 48, "pm25_2024": 28, "urban": False},
}

months = pd.date_range("2015-01", "2024-12", freq="MS")
records = []

for city, info in cities.items():
    for date in months:
        year = date.year
        month = date.month
        t = (year - 2015) + (month - 1) / 12  # years since 2015

        # PM2.5: linear decline with seasonal variation
        pm25_base = info["pm25_2015"] + (info["pm25_2024"] - info["pm25_2015"]) * t / 9.917
        # Winter peak (Dec-Feb), summer trough (Jun-Aug)
        seasonal = 8 * np.cos(2 * np.pi * (month - 1) / 12) + 3 * np.cos(4 * np.pi * (month - 1) / 12)
        # COVID dip: Feb-Apr 2020
        covid = -8 if (year == 2020 and month in [2, 3, 4]) else 0
        pm25 = max(5, pm25_base + seasonal + covid + np.random.normal(0, 3))

        # PM10: correlated with PM2.5, ratio ~1.5-1.8
        pm10 = pm25 * np.random.uniform(1.4, 1.9)

        # NO2: declining trend, strong urban signal
        no2_base = (35 if info["urban"] else 22) - t * 1.2
        no2_seasonal = 6 * np.cos(2 * np.pi * (month - 1) / 12)
        no2_covid = -12 if (year == 2020 and month in [2, 3]) else 0
        no2 = max(5, no2_base + no2_seasonal + no2_covid + np.random.normal(0, 4))

        # SO2: steep decline (clean coal / desulfurization)
        so2_base = (18 - t * 1.5) * (1.2 if info["urban"] else 1.0)
        so2 = max(3, so2_base + np.random.normal(0, 2))

        # O3: RISING trend (counter to other pollutants)
        o3_base = 75 + t * 2.5
        # O3 peaks in summer (Apr-Sep), photochemical
        o3_seasonal = 30 * np.cos(2 * np.pi * (month - 7) / 12)
        o3 = max(20, o3_base + o3_seasonal + np.random.normal(0, 8))

        # CO: slow decline
        co_base = 1.1 - t * 0.04
        co = max(0.3, co_base + 0.15 * np.cos(2 * np.pi * (month - 1) / 12) + np.random.normal(0, 0.08))

        # AQI: simplified calculation (dominant pollutant approach)
        aqi = max(pm25 * 1.5, o3 * 0.6, no2 * 1.2, pm10 * 0.8)
        aqi = max(20, min(300, aqi + np.random.normal(0, 5)))

        records.append({
            "date": date.strftime("%Y-%m"),
            "city": city,
            "city_zh": {"Guangzhou": "广州", "Shenzhen": "深圳", "Zhuhai": "珠海",
                        "Foshan": "佛山", "Huizhou": "惠州", "Dongguan": "东莞",
                        "Zhongshan": "中山", "Jiangmen": "江门", "Zhaoqing": "肇庆"}[city],
            "lat": info["lat"],
            "lon": info["lon"],
            "AQI": round(aqi, 1),
            "PM2.5": round(pm25, 1),
            "PM10": round(pm10, 1),
            "SO2": round(so2, 1),
            "NO2": round(no2, 1),
            "CO": round(co, 2),
            "O3": round(o3, 1),
        })

df = pd.DataFrame(records)
df.to_csv("../data/gba_air_quality_2015_2024.csv", index=False)
print(f"Generated {len(df)} records for {len(cities)} cities over {len(months)} months.")
print(f"\nSample data:")
print(df.head(12).to_string(index=False))
print(f"\nPM2.5 summary by city:")
print(df.groupby("city")["PM2.5"].agg(["mean", "min", "max"]).round(1).to_string())
