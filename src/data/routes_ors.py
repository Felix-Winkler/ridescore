"""OpenRouteService client: round trips with geometry and elevation."""
from __future__ import annotations

from typing import Any, Optional

from data.cache import Cache
from data.errors import DataError
from data.http import HttpClient
from models.models import LatLon, Route

# (verify) against https://openrouteservice.org/dev/#/api-docs/v2/directions
URL = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
MAIN_ROAD_WAYTYPE = 1  # ORS waytype 1 = "State road" (motorway / main road)


def parse_route(payload: dict[str, Any], route_id: str, name: str) -> Route:
    """Validate an ORS GeoJSON response and convert it to a Route."""
    try:
        feature = payload["features"][0]
        raw = feature["geometry"]["coordinates"]
        summary = feature["properties"]["summary"]
        coords = [LatLon(c[1], c[0]) for c in raw]
        elevations = [float(c[2]) for c in raw if len(c) > 2]
        distance_km = float(summary["distance"]) / 1000
        duration_min = float(summary["duration"]) / 60
    except (KeyError, IndexError, TypeError, ValueError) as ex:
        raise DataError(f"Unexpected route response: {ex!r}") from ex
    if len(coords) < 2 or distance_km <= 0:
        raise DataError("Route is empty.")

    share = 0.0
    try:  # optional: share of main roads from the 'waytype' extra info
        values = feature["properties"]["extras"]["waytype"]["values"]
        n = len(coords)
        main = sum(end - start for start, end, kind in values if kind == MAIN_ROAD_WAYTYPE)
        share = max(0.0, min(1.0, main / max(1, n - 1)))
    except (KeyError, TypeError, ValueError):
        pass
    return Route(id=route_id, name=name, coords=coords,
                 elevations=elevations if len(elevations) == len(coords) else [],
                 distance_km=distance_km, duration_min=duration_min,
                 main_road_share=share, source="ors")


class OrsClient:
    """Fetches round trips. Different seeds give different loops."""

    def __init__(self, api_key: str, http: HttpClient, cache: Optional[Cache] = None) -> None:
        self.api_key = api_key
        self.http = http
        self.cache = cache

    def round_trip(self, start: LatLon, length_km: float, seed: int, route_id: str,
                   name: str) -> Route:
        body = {
            "coordinates": [[start.lon, start.lat]],
            "options": {"round_trip": {"length": int(length_km * 1000), "points": 5,
                                       "seed": seed}},
            "elevation": True,
            "extra_info": ["waytype"],
            "instructions": False,
        }
        payload = self.cache.get(body) if self.cache else None
        if payload is None:
            payload = self.http.post_json(URL, body, headers={"Authorization": self.api_key})
            if self.cache:
                self.cache.set(body, payload)
        return parse_route(payload, route_id, name)
