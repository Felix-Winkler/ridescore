"""Dataclasses shared by all layers (no logic except (de)serialisation)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=True)
class LatLon:
    """A WGS84 coordinate."""

    lat: float
    lon: float


@dataclass(frozen=True)
class Place:
    """A search result for a place name."""

    label: str
    location: LatLon


@dataclass
class Route:
    """A round trip with geometry, elevation and basic statistics."""

    id: str
    name: str
    coords: list[LatLon]
    elevations: list[float]  # metres, same length as coords (may be empty)
    distance_km: float
    duration_min: float
    main_road_share: float = 0.0  # 0..1, share of motorway / main road
    source: str = "ors"  # "ors" or "demo"


@dataclass
class WeatherPoint:
    """Forecast at one point of a route, at the time the rider passes it."""

    km: float
    time: datetime
    lat: float
    lon: float
    temp_c: float
    precip_mm: float  # mm per hour
    wind_kmh: float


@dataclass
class TrafficInfo:
    """Traffic situation of a route. congestion_factor 1.0 = free flow."""

    congestion_factor: float
    source: str  # "EVIS.AT", "Google", "Estimate"
    estimated: bool = False


@dataclass
class Roadwork:
    """A roadwork / closure near a route."""

    location: LatLon
    description: str


@dataclass
class RouteScore:
    """Scores from 1 to 5. weather is None when no forecast was available."""

    curves: float
    weather: Optional[float]
    traffic: float
    overall: float
    traffic_source: str = "Estimate"
    weather_source: str = "none"
    warnings: list[str] = field(default_factory=list)


@dataclass
class ScoredRoute:
    """A route together with everything computed for it."""

    route: Route
    score: RouteScore
    weather_points: list[WeatherPoint] = field(default_factory=list)
    roadworks: list[Roadwork] = field(default_factory=list)


@dataclass
class Weights:
    """User weights for the overall score."""

    curves: float = 1.0
    weather: float = 1.0
    traffic: float = 1.0


@dataclass
class SearchParams:
    """Everything the user enters on the input screen."""

    start: LatLon
    length_km: float
    start_time: datetime
    n_routes: int = 4


@dataclass
class Settings:
    """Persistent user settings."""

    weights: Weights = field(default_factory=Weights)
    home: str = ""
    length_km: float = 100.0
    n_routes: int = 4


# ---------------------------------------------------------------- serialisation

def scored_route_to_dict(sr: ScoredRoute) -> dict[str, Any]:
    """Convert a ScoredRoute to JSON-friendly data (weather points are dropped)."""
    r, s = sr.route, sr.score
    return {
        "route": {
            "id": r.id, "name": r.name,
            "coords": [[p.lat, p.lon] for p in r.coords],
            "elevations": r.elevations,
            "distance_km": r.distance_km, "duration_min": r.duration_min,
            "main_road_share": r.main_road_share, "source": r.source,
        },
        "score": {
            "curves": s.curves, "weather": s.weather, "traffic": s.traffic,
            "overall": s.overall, "traffic_source": s.traffic_source,
            "weather_source": s.weather_source, "warnings": s.warnings,
        },
        "roadworks": [
            {"lat": w.location.lat, "lon": w.location.lon, "description": w.description}
            for w in sr.roadworks
        ],
    }


def scored_route_from_dict(d: dict[str, Any]) -> ScoredRoute:
    """Inverse of :func:`scored_route_to_dict`. Raises KeyError/ValueError on bad data."""
    r, s = d["route"], d["score"]
    route = Route(
        id=str(r["id"]), name=str(r["name"]),
        coords=[LatLon(float(a), float(b)) for a, b in r["coords"]],
        elevations=[float(e) for e in r.get("elevations", [])],
        distance_km=float(r["distance_km"]), duration_min=float(r["duration_min"]),
        main_road_share=float(r.get("main_road_share", 0.0)),
        source=str(r.get("source", "ors")),
    )
    score = RouteScore(
        curves=float(s["curves"]),
        weather=None if s.get("weather") is None else float(s["weather"]),
        traffic=float(s["traffic"]), overall=float(s["overall"]),
        traffic_source=str(s.get("traffic_source", "Estimate")),
        weather_source=str(s.get("weather_source", "none")),
        warnings=[str(w) for w in s.get("warnings", [])],
    )
    works = [
        Roadwork(LatLon(float(w["lat"]), float(w["lon"])), str(w["description"]))
        for w in d.get("roadworks", [])
    ]
    return ScoredRoute(route=route, score=score, roadworks=works)


def settings_to_dict(s: Settings) -> dict[str, Any]:
    return {
        "weights": {"curves": s.weights.curves, "weather": s.weights.weather,
                    "traffic": s.weights.traffic},
        "home": s.home, "length_km": s.length_km, "n_routes": s.n_routes,
    }


def settings_from_dict(d: dict[str, Any]) -> Settings:
    w = d.get("weights", {})
    return Settings(
        weights=Weights(float(w.get("curves", 1)), float(w.get("weather", 1)),
                        float(w.get("traffic", 1))),
        home=str(d.get("home", "")),
        length_km=float(d.get("length_km", 100)),
        n_routes=int(d.get("n_routes", 4)),
    )
