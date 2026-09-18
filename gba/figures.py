"""The five figures, each answering one question from the analysis tables."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import analysis, metrics

OUT = Path(__file__).resolve().parents[1] / "outputs"

plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 150, "font.size": 9,
    "axes.grid": True, "grid.alpha": 0.25,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": "white",
})

REGION = "#b91c1c"
CITY = "#94a3b8"
PM = "#0369a1"
OZONE = "#c2410c"


def _save(fig, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def diverging_trends(years: pd.DataFrame) -> Path:
    """PM2.5 falling while ozone rises: the regional story in one panel."""
    region = analysis.regional(years).set_index("year")
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    for column, colour, label in (
        ("PM2.5", PM, "PM2.5, annual mean"),
        ("O3_MDA8_P90", OZONE, "O3, 90th percentile of daily MDA8"),
    ):
        series = region[column].dropna()
        index = 100.0 * series / series.iloc[0]
        # Start and end values go in the legend: both series begin at 100, so
        # labels on the first point would sit on top of each other.
        ax.plot(index.index, index.values, marker="o", color=colour, linewidth=2.2,
                label=f"{label}: {series.iloc[0]:.0f} → {series.iloc[-1]:.0f} µg/m³")
    ax.axhline(100, color="#64748b", linewidth=0.8, linestyle=":")
    ax.set_ylabel(f"Index, {int(region.index.min())} = 100")
    ax.set_title("Greater Bay Area, nine-city mean: particulates down, ozone not", fontsize=10.5)
    ax.legend(frameon=False, loc="lower left")
    ax.set_xticks(region.index)
    return _save(fig, "pm25_vs_ozone_index.png")


def pm25_by_city(years: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    for city, group in years.groupby("city"):
        ax.plot(group["year"], group["PM2.5"], color=CITY, linewidth=1.0, alpha=0.9)
        last = group.dropna(subset=["PM2.5"]).iloc[-1]
        ax.annotate(city, (last["year"], last["PM2.5"]), textcoords="offset points",
                    xytext=(4, -2), fontsize=7, color="#475569")
    region = analysis.regional(years)
    ax.plot(region["year"], region["PM2.5"], color=REGION, linewidth=2.6, label="nine-city mean")
    ax.axhline(metrics.GRADE_II["PM2.5"], color="#0f172a", linewidth=0.9, linestyle="--")
    ax.annotate("GB 3095 Grade II, 35 µg/m³", (years["year"].min(), metrics.GRADE_II["PM2.5"]),
                textcoords="offset points", xytext=(2, 4), fontsize=7.5)
    ax.set_ylabel("PM2.5 annual mean (µg/m³)")
    ax.set_title("PM2.5 by city, 2015–2024", fontsize=10.5)
    ax.set_xticks(sorted(years["year"].unique()))
    ax.set_xlim(years["year"].min() - 0.3, years["year"].max() + 1.2)
    ax.legend(frameon=False)
    return _save(fig, "pm25_trend_all_cities.png")


def trend_heatmap(years: pd.DataFrame) -> Path:
    """Change over the decade for every city and pollutant, with significance."""
    table = analysis.trends(years)
    pivot = table.pivot(index="city", columns="pollutant", values="change_pct")[analysis.ASSESSED]
    pvals = table.pivot(index="city", columns="pollutant", values="p")[analysis.ASSESSED]
    order = [c for c in pivot.index if not c.startswith("GBA")] + ["GBA (9-city mean)"]
    pivot, pvals = pivot.loc[order], pvals.loc[order]

    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    limit = np.nanmax(np.abs(pivot.to_numpy()))
    image = ax.imshow(pivot.to_numpy(), cmap="RdBu_r", vmin=-limit, vmax=limit, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([analysis.LABEL[c] for c in pivot.columns], rotation=25, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            value, p = pivot.iat[i, j], pvals.iat[i, j]
            if np.isfinite(value):
                mark = "*" if p < 0.05 else ""
                text = "0%" if abs(value) < 0.5 else f"{value:+.0f}%"  # never "-0%"
                ax.text(j, i, f"{text}{mark}", ha="center", va="center", fontsize=7.5,
                        color="white" if abs(value) > 0.55 * limit else "#0f172a")
    ax.grid(False)
    ax.axhline(len(order) - 1.5, color="#0f172a", linewidth=1.2)  # cities above, region below
    fig.colorbar(image, ax=ax, label="Theil–Sen change over the record (%)", shrink=0.85)
    ax.set_title("Change over 2015–2024 (* Mann–Kendall p < 0.05)", fontsize=10.5)
    return _save(fig, "pollutant_trend_heatmap.png")


def seasonal_cycle(months: pd.DataFrame) -> Path:
    cycle = analysis.seasonal_cycle(months)
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.plot(cycle.index, cycle["PM2.5"], marker="o", color=PM, linewidth=2, label="PM2.5")
    ax.plot(cycle.index, cycle["O3_MDA8"], marker="o", color=OZONE, linewidth=2, label="O3 (MDA8)")
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    ax.set_ylabel("µg/m³, mean over 2015–2024 and nine cities")
    ax.set_title("Seasonal cycle: the two problems peak in different months", fontsize=10.5)
    ax.legend(frameon=False)
    return _save(fig, "seasonal_cycle.png")


def lockdown(days: pd.DataFrame) -> Path:
    calendar = analysis.lockdown_february(days)
    aligned = analysis.lockdown_holiday_aligned(days)
    order = ["NO2", "CO", "PM2.5", "PM10", "SO2", "O3_MDA8"]
    x = np.arange(len(order))
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.bar(x - 0.2, calendar.loc[order, "change_pct"], 0.4, color="#cbd5e1",
           label="Feb 2020 vs Feb 2017–19 (calendar month)")
    ax.bar(x + 0.2, aligned.loc[order, "change_pct"], 0.4, color=REGION,
           label="Aligned on Spring Festival (days 8–37 after)")
    ax.axhline(0, color="#0f172a", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([analysis.LABEL[p] for p in order])
    ax.set_ylabel("Change vs 2017–2019 (%)")
    ax.set_title("The 2020 lockdown, with and without the holiday held fixed", fontsize=10.5)
    ax.legend(frameon=False, fontsize=8)
    return _save(fig, "covid_impact.png")


def against_standard(years: pd.DataFrame, year: int) -> Path:
    table = analysis.against_standard(years, year)
    columns = ["PM2.5", "PM10", "NO2", "O3_MDA8_P90"]
    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    width = 0.2
    colours = [PM, "#0ea5e9", "#6366f1", OZONE]
    for k, (column, colour) in enumerate(zip(columns, colours)):
        ax.bar(np.arange(len(table)) + (k - 1.5) * width, table[column], width,
               color=colour, label=analysis.LABEL[column])
    ax.axhline(100, color="#0f172a", linewidth=1, linestyle="--")
    ax.annotate("Grade II limit", (len(table) - 0.5, 100), textcoords="offset points",
                xytext=(0, 3), ha="right", fontsize=7.5)
    ax.set_xticks(np.arange(len(table)))
    ax.set_xticklabels(table.index, rotation=20, ha="right")
    ax.set_ylabel("Assessed value as % of limit")
    ax.set_title(f"{year} against GB 3095-2012 Grade II", fontsize=10.5)
    ax.legend(frameon=False, fontsize=7.5, ncol=4, loc="upper left")
    return _save(fig, "vs_standard.png")


def all_figures(latest_year: int) -> list[Path]:
    days, months, years = analysis.load()
    return [
        diverging_trends(years), pm25_by_city(years), trend_heatmap(years),
        seasonal_cycle(months), lockdown(days), against_standard(years, latest_year),
    ]
