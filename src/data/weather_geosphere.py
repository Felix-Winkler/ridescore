"""GeoSphere Austria Data Hub: hourly forecast (licence CC BY 4.0, credit GeoSphere Austria).

Dataset nwp-v2-1h-1km (successor of the outdated nwp-v1-1h-2500m). Parameters used:
2t = temperature (deg C), tp = total precipitation in the last hour (kg/m2 = mm, rain + snow),
10u / 10v = wind components at 10 m (m/s).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import hypot
from typing import Any, Optional

from data.cache import Cache
from data.errors import DataError
from data.http import HttpClient
from models.models import LatLon, WeatherPoint

URL = "https://dataset.api.hub.geosphere.at/v1/timeseries/forecast/nwp-v2-1h-1km"
P_TEMP, P_PRECIP, P_U, P_V = "2t", "tp", "10u", "10v"
PARAMETERS = [P_TEMP, P_PRECIP, P_U, P_V]

# A target is (km along the route, point, time the rider passes it)
Target = tuple[float, LatLon, datetime]


def _utc(dt: datetime) -> datetime:
    """Naive datetimes are treated as local time."""
    return (dt if dt.tzinfo else dt.astimezone()).astimezone(timezone.utc)


def _series(feature: dict[str, Any], n: int) -> dict[str, list]:
    """Data lists of one feature; every list must have one value per timestamp."""
    params = feature["properties"]["parameters"]
    series = {k: params[k]["data"] for k in PARAMETERS}
    if any(len(v) != n for v in series.values()):
        raise ValueError("series length mismatch")
    return series


def _values_at(series: dict[str, list], i: int) -> Optional[tuple[float, float, float]]:
    """(temp deg C, precip mm/h, wind km/h) at index i, or None if the hour is incomplete."""
    temp, precip = series[P_TEMP][i], series[P_PRECIP][i]
    u, v = series[P_U][i], series[P_V][i]
    if temp is None or u is None or v is None:
        return None
    return float(temp), float(precip or 0.0), hypot(u, v) * 3.6


def _timestamps(payload: dict[str, Any]) -> list[datetime]:
    stamps = [datetime.fromisoformat(t) for t in payload["timestamps"]]
    if not stamps:
        raise DataError("The forecast service returned no data for this time (dataset outdated?).")
    return stamps


def parse_forecast(payload: dict[str, Any], targets: list[Target]) -> list[WeatherPoint]:
    """Pick, for every target, the forecast hour closest to the passing time."""
    try:
        stamps = _timestamps(payload)
        feats = payload["features"]
        if len(feats) != len(targets):
            raise ValueError("feature count does not match requested points")
        out: list[WeatherPoint] = []
        for (km, pt, when), feat in zip(targets, feats):
            series = _series(feat, len(stamps))
            when_utc = _utc(when)
            i = min(range(len(stamps)), key=lambda j: abs(_utc(stamps[j]) - when_utc))
            vals = _values_at(series, i)
            if vals:  # incomplete hour: skip this point
                out.append(WeatherPoint(km=km, time=when, lat=pt.lat, lon=pt.lon,
                                        temp_c=vals[0], precip_mm=vals[1], wind_kmh=vals[2]))
        return out
    except (KeyError, IndexError, TypeError, ValueError) as ex:
        raise DataError(f"Unexpected weather response: {ex!r}") from ex


def parse_hourly(payload: dict[str, Any], start: datetime, hours: int) -> list[WeatherPoint]:
    """Hourly forecast for ONE location: every hour from ``start`` to ``start + hours``.

    ``WeatherPoint.km`` holds the hours since ``start`` (there is no route here).
    """
    try:
        stamps = _timestamps(payload)
        series = _series(payload["features"][0], len(stamps))
        start_utc = _utc(start)
        out: list[WeatherPoint] = []
        for i, ts in enumerate(stamps):
            offset_h = (_utc(ts) - start_utc).total_seconds() / 3600
            vals = _values_at(series, i)
            if vals and -0.5 <= offset_h <= hours:
                out.append(WeatherPoint(km=max(0.0, offset_h), time=_utc(ts), lat=0.0, lon=0.0,
                                        temp_c=vals[0], precip_mm=vals[1], wind_kmh=vals[2]))
        return out
    except (KeyError, IndexError, TypeError, ValueError) as ex:
        raise DataError(f"Unexpected weather response: {ex!r}") from ex

class GeoSphereClient:
    """Fetches the forecast for several points in one request."""

    def __init__(self, http: HttpClient, cache: Optional[Cache] = None) -> None:
        self.http = http
        self.cache = cache

    def hourly(self, point: LatLon, start: datetime, hours: int = 12) -> list[WeatherPoint]:
        """Rough hourly forecast at one place (used for the preview on the input screen)."""
        start_u = _utc(start)
        begin = start_u.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        end = start_u + timedelta(hours=hours + 1)
        params: list[tuple[str, str]] = [("parameters", p) for p in PARAMETERS]
        params += [("lat_lon", f"{point.lat:.4f},{point.lon:.4f}"),
                   ("start", begin.strftime("%Y-%m-%dT%H:%M")),
                   ("end", end.strftime("%Y-%m-%dT%H:%M")), ("output_format", "geojson")]
        payload = self.cache.get(params) if self.cache else None
        if payload is None:
            payload = self.http.get_json(URL, params=params)
            if self.cache:
                self.cache.set(params, payload)
        return parse_hourly(payload, start, hours)

    def forecast(self, targets: list[Target]) -> list[WeatherPoint]:
        if not targets:
            return []
        times = [_utc(t[2]) for t in targets]
        start = min(times).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        end = max(times).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        params: list[tuple[str, str]] = [("parameters", p) for p in PARAMETERS]
        params += [("lat_lon", f"{t[1].lat:.4f},{t[1].lon:.4f}") for t in targets]
        params += [("start", start.strftime("%Y-%m-%dT%H:%M")),
                   ("end", end.strftime("%Y-%m-%dT%H:%M")), ("output_format", "geojson")]
        payload = self.cache.get(params) if self.cache else None
        if payload is None:
            payload = self.http.get_json(URL, params=params)
            if self.cache:
                self.cache.set(params, payload)
        return parse_forecast(payload, targets)
