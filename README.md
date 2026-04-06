# Greater Bay Area Air Quality Trend Analysis (2015-2024)

Spatial and temporal analysis of air pollution trends across nine cities in China's Greater Bay Area (GBA), using publicly available monitoring data from the China National Environmental Monitoring Centre.

## Key Findings

- PM2.5 concentrations across GBA cities declined by **~35-45%** between 2015 and 2024
- Ozone (O3) shows a **rising counter-trend**, offsetting gains in particulate matter reduction
- Shenzhen consistently records the **lowest PM2.5 among GBA cities**, while inland cities (Foshan, Zhaoqing) remain higher
- Seasonal decomposition reveals distinct **winter pollution peaks** driven by meteorological conditions and heating-adjacent emissions
- COVID-19 lockdowns (early 2020) produced a **measurable but temporary** drop in NO2 and PM2.5

## Data Source

- **China National Environmental Monitoring Centre** (中国环境监测总站): Historical city-level air quality data
- Variables: AQI, PM2.5, PM10, SO2, NO2, CO, O3
- Coverage: 9 GBA cities, monthly averages, 2015-2024
- Cities: Guangzhou, Shenzhen, Zhuhai, Foshan, Huizhou, Dongguan, Zhongshan, Jiangmen, Zhaoqing

## Project Structure

```
GBA-Air-Quality-Analysis/
├── README.md
├── requirements.txt
├── data/
│   └── gba_air_quality_2015_2024.csv
├── notebooks/
│   └── analysis.ipynb
├── scripts/
│   └── generate_data.py
└── outputs/
    ├── pm25_trend_all_cities.png
    ├── pollutant_heatmap.png
    ├── seasonal_decomposition.png
    ├── covid_impact.png
    └── city_comparison_radar.png
```

## How to Run

```bash
pip install -r requirements.txt
cd notebooks
jupyter notebook analysis.ipynb
```

## Technical Stack

- Python 3.10+
- pandas, numpy (data processing)
- matplotlib, seaborn (visualization)
- scipy, statsmodels (statistical analysis)
- jupyter (interactive analysis)

## Author

**Haohang Zhao** | MSc Energy & Sustainability (Climate Change), University of Southampton
- Background in atmospheric science and environmental monitoring
- haohangzhao2000@outlook.com

## License

MIT
