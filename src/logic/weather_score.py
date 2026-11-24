"""Weather score from forecast points along the route."""
from __future__ import annotations

from typing import Optional

from logic.scaling import clamp_score
from models.models import WeatherPoint

IDEAL_TEMP = (15.0, 27.0)
WIND_OK_KMH = 25.0
WORST_WEIGHT = 0.6  # rain anywhere matters: worst point weighs more than the mean


def point_score(p: WeatherPoint) -> float:
    """Score 1..5 for one forecast point."""
    s = 5.0
    if p.precip_mm >= 0.1:
        s -= 2.0 + min(2.0, p.precip_mm * 2.0)
    low, high = IDEAL_TEMP
    dev = low - p.temp_c if p.temp_c < low else max(0.0, p.temp_c - high)
    s -= min(2.0, dev * 0.15)
    if p.wind_kmh > WIND_OK_KMH:
        s -= min(1.5, (p.wind_kmh - WIND_OK_KMH) * 0.05)
    return clamp_score(s)


def describe_weather(points: list[WeatherPoint]) -> str:
    """One-line summary like 'Dry, 14-19 °C, wind up to 22 km/h'."""
    if not points:
        return "No forecast available."
    rain_hours = sum(1 for p in points if p.precip_mm >= 0.1)
    rain = ("Dry" if rain_hours == 0 else
            f"Rain in {rain_hours} of {len(points)} hours ({max(p.precip_mm for p in points):.1f} mm/h max)")
    lo, hi = min(p.temp_c for p in points), max(p.temp_c for p in points)
    return f"{rain}, {lo:.0f}-{hi:.0f} °C, wind up to {max(p.wind_kmh for p in points):.0f} km/h"


def weather_score(points: list[WeatherPoint]) -> Optional[float]:
    """Mix of worst and average point score; None if there is no data."""
    if not points:
        return None
    scores = [point_score(p) for p in points]
    return clamp_score(WORST_WEIGHT * min(scores) + (1 - WORST_WEIGHT) * sum(scores) / len(scores))
