"""Curve score: how twisty and hilly is a route?"""
from __future__ import annotations

from logic.geo import angle_diff, bearing_deg, cumulative_km, resample
from logic.scaling import clamp_score, scale_to_score
from models.models import LatLon

# Starting values - calibrate with known roads (pass road ~5, straight B-road 1-2).
WORST_DEG_PER_KM = 30.0
BEST_DEG_PER_KM = 180.0
STEP_KM = 0.1
NOISE_DEG = 1.5


def curviness_deg_per_km(coords: list[LatLon], step_km: float = STEP_KM,
                         noise_deg: float = NOISE_DEG) -> float:
    """Sum of absolute heading changes per km, ignoring tiny changes (GPS noise)."""
    pts = resample(coords, step_km)
    if len(pts) < 3:
        return 0.0
    headings = [bearing_deg(a, b) for a, b in zip(pts, pts[1:])]
    total = 0.0
    for h1, h2 in zip(headings, headings[1:]):
        d = abs(angle_diff(h1, h2))
        if d >= noise_deg:
            total += d
    length = cumulative_km(pts)[-1]
    return total / length if length > 0 else 0.0


def elevation_gain_m(elevations: list[float]) -> float:
    """Total ascent in metres."""
    return sum(max(0.0, b - a) for a, b in zip(elevations, elevations[1:]))


def curve_score(coords: list[LatLon], elevations: list[float],
                main_road_share: float = 0.0) -> float:
    """Score 1..5. Twisty = high; hills give a bonus, motorway share a penalty."""
    length = cumulative_km(coords)[-1] if len(coords) > 1 else 0.0
    if length <= 0:
        return 1.0
    base = scale_to_score(curviness_deg_per_km(coords), WORST_DEG_PER_KM, BEST_DEG_PER_KM)
    bonus = min(0.5, elevation_gain_m(elevations) / length / 100.0)  # 50 m/km -> +0.5
    penalty = 2.0 * max(0.0, min(1.0, main_road_share))
    return clamp_score(base + bonus - penalty)
