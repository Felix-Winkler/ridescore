"""Google Routes API: traffic-aware duration vs. free-flow duration (optional, needs a key)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from data.errors import DataError, DataUnavailable
from data.http import HttpClient
from logic.geo import sample_along
from models.models import LatLon, Route, TrafficInfo

# (verify) https://developers.google.com/maps/documentation/routes
URL = "https://routes.googleapis.com/directions/v2:computeRoutes"


def _seconds(value: str) -> float:
    """Parse durations like '1234s'."""
    return float(str(value).rstrip("s"))


def _waypoint(p: LatLon) -> dict:
    return {"location": {"latLng": {"latitude": p.lat, "longitude": p.lon}}}


class GoogleProvider:
    name = "Google"

    def __init__(self, api_key: str, http: HttpClient) -> None:
        self.api_key = api_key
        self.http = http

    def get_traffic(self, route: Route, start_time: datetime) -> TrafficInfo:
        if not self.api_key:
            raise DataUnavailable("no GOOGLE_API_KEY set")
        picks = [p for _, p in sample_along(route.coords, max(route.distance_km / 8, 1.0))]
        mids = picks[1:-1][:20]
        when = max(start_time.astimezone(timezone.utc), datetime.now(timezone.utc) + timedelta(minutes=1))
        body = {
            "origin": _waypoint(route.coords[0]),
            "destination": _waypoint(route.coords[-1]),
            "intermediates": [_waypoint(p) for p in mids],
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE",
            "departureTime": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        headers = {"X-Goog-Api-Key": self.api_key,
                   "X-Goog-FieldMask": "routes.duration,routes.staticDuration"}
        data = self.http.post_json(URL, body, headers=headers)
        try:
            r = data["routes"][0]
            factor = _seconds(r["duration"]) / _seconds(r["staticDuration"])
        except (KeyError, IndexError, ValueError, ZeroDivisionError) as ex:
            raise DataError(f"unexpected response: {ex!r}") from ex
        return TrafficInfo(max(1.0, factor), source="Google")
