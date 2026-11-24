"""Small geographic helpers (pure functions)."""
from __future__ import annotations

from math import asin, atan2, cos, degrees, radians, sin, sqrt

from models.models import LatLon

EARTH_KM = 6371.0088


def haversine_km(a: LatLon, b: LatLon) -> float:
    """Great-circle distance between two points in km."""
    dlat = radians(b.lat - a.lat)
    dlon = radians(b.lon - a.lon)
    h = sin(dlat / 2) ** 2 + cos(radians(a.lat)) * cos(radians(b.lat)) * sin(dlon / 2) ** 2
    return 2 * EARTH_KM * asin(sqrt(h))


def bearing_deg(a: LatLon, b: LatLon) -> float:
    """Initial bearing from a to b in degrees (0..360)."""
    dlon = radians(b.lon - a.lon)
    y = sin(dlon) * cos(radians(b.lat))
    x = cos(radians(a.lat)) * sin(radians(b.lat)) - sin(radians(a.lat)) * cos(radians(b.lat)) * cos(dlon)
    return (degrees(atan2(y, x)) + 360) % 360


def angle_diff(a: float, b: float) -> float:
    """Signed smallest difference b - a in degrees, in (-180, 180]."""
    d = (b - a + 180) % 360 - 180
    return 180.0 if d == -180 else d


def cumulative_km(coords: list[LatLon]) -> list[float]:
    """Distance from the start for every point of the polyline."""
    out = [0.0]
    for p, q in zip(coords, coords[1:]):
        out.append(out[-1] + haversine_km(p, q))
    return out


def resample(coords: list[LatLon], step_km: float) -> list[LatLon]:
    """Return points spaced ``step_km`` apart along the polyline (first and last included)."""
    if len(coords) < 2 or step_km <= 0:
        return list(coords)
    out = [coords[0]]
    carry = 0.0  # distance already walked since the last emitted point
    for p, q in zip(coords, coords[1:]):
        seg = haversine_km(p, q)
        if seg == 0:
            continue
        pos = step_km - carry
        while pos <= seg:
            t = pos / seg
            out.append(LatLon(p.lat + (q.lat - p.lat) * t, p.lon + (q.lon - p.lon) * t))
            pos += step_km
        carry = seg - (pos - step_km)
    if out[-1] != coords[-1]:
        out.append(coords[-1])
    return out


def sample_along(coords: list[LatLon], step_km: float) -> list[tuple[float, LatLon]]:
    """Pick (km_from_start, point) roughly every ``step_km`` using the original vertices."""
    if not coords:
        return []
    cum = cumulative_km(coords)
    picks = [(0.0, coords[0])]
    next_km = step_km
    for km, p in zip(cum, coords):
        if km >= next_km:
            picks.append((km, p))
            next_km = km + step_km
    return picks


def min_distance_km(point: LatLon, coords: list[LatLon]) -> float:
    """Distance from a point to the closest vertex of a (dense) polyline."""
    if not coords:
        return float("inf")
    return min(haversine_km(point, c) for c in coords)


def bounds(coords: list[LatLon]) -> tuple[float, float, float, float]:
    """(min_lat, min_lon, max_lat, max_lon) of a list of points."""
    lats = [c.lat for c in coords]
    lons = [c.lon for c in coords]
    return min(lats), min(lons), max(lats), max(lons)
