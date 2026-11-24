"""Generated demo data so the whole app works without any API key."""
from __future__ import annotations

import zlib
from datetime import datetime, timedelta
from math import cos, pi, sin

from models.models import LatLon, Roadwork, Route, WeatherPoint

# (wiggle amplitude in km, wiggle frequency): smooth loops ... very twisty loops
STYLES = [(0.00, 7), (0.05, 25), (0.12, 45), (0.20, 70), (0.28, 95)]


def mock_route(start: LatLon, length_km: float, seed: int, route_id: str, name: str) -> Route:
    """A closed loop through ``start`` whose twistiness depends on the seed."""
    amp, freq = STYLES[seed % len(STYLES)]
    radius = length_km / (2 * pi)
    phase = 1.3 * (seed + 1)
    n = max(400, int(length_km * 12))
    km_per_deg_lat = 111.2
    km_per_deg_lon = 111.2 * cos(start.lat * pi / 180)
    coords, elev = [], []
    for i in range(n + 1):
        t = 2 * pi * i / n
        r = radius * (1 + 0.25 * sin(2 * t + phase)) + amp * sin(freq * t)
        # circle through the start point: centre is shifted by one radius
        x = r * cos(t) - radius
        y = r * sin(t)
        coords.append(LatLon(start.lat + y / km_per_deg_lat, start.lon + x / km_per_deg_lon))
        elev.append(450 + 180 * (1 + sin(3 * t + phase)) / 2 * (1 + seed % 3) + 40 * sin(11 * t))
    coords[-1] = coords[0]
    return Route(id=route_id, name=name, coords=coords, elevations=elev,
                 distance_km=length_km, duration_min=length_km / 55 * 60,
                 main_road_share=[0.0, 0.1, 0.05, 0.0, 0.3][seed % 5], source="demo")


def mock_weather(route: Route, targets: list[tuple[float, LatLon, datetime]],
                 seed: int) -> list[WeatherPoint]:
    """Deterministic fake weather; every second route gets a rain shower."""
    rng = zlib.crc32(route.id.encode())
    out = []
    for i, (km, p, when) in enumerate(targets):
        temp = 12 + (rng % 9) + 6 * sin(i / 2)
        rain = 1.2 if seed % 2 == 1 and i == len(targets) // 2 else 0.0
        out.append(WeatherPoint(km=km, time=when, lat=p.lat, lon=p.lon, temp_c=temp,
                                precip_mm=rain, wind_kmh=8 + (rng >> 4) % 20))
    return out


def mock_roadworks(route: Route, seed: int) -> list[Roadwork]:
    """One fake roadwork on every third route (to demonstrate warnings)."""
    if seed % 3 != 2:
        return []
    mid = route.coords[len(route.coords) // 3]
    return [Roadwork(mid, "Demo roadwork: lane closed, expect delays")]
