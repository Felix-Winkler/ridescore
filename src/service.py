"""Orchestrates the 'rate a route' feature: routes -> weather/traffic/roadworks -> scores."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

from data import mock
from data.cache import Cache
from data.config import Config
from data.errors import DataError
from data.http import HttpClient
from data.roadworks_asfinag import fetch_roadworks
from data.routes_ors import OrsClient
from data.storage import default_dir
from data.traffic_base import TrafficProvider, traffic_with_fallback
from data.traffic_estimate import EstimateProvider
from data.traffic_evis import EvisProvider
from data.traffic_google import GoogleProvider
from data.weather_geosphere import GeoSphereClient
from logic.curves import curve_score
from logic.geo import min_distance_km, resample, sample_along
from logic.ranking import overall_score, rank_routes
from logic.traffic_score import traffic_score
from logic.weather_score import weather_score
from models.models import (Roadwork, Route, RouteScore, ScoredRoute, SearchParams,
                           Weights)

WEATHER_STEP_KM = 12.0
ROADWORK_RADIUS_KM = 0.3
ROUTE_NAMES = ["Loop A", "Loop B", "Loop C", "Loop D", "Loop E"]


@dataclass
class SearchResult:
    """Ranked routes plus messages the UI should show."""

    routes: list[ScoredRoute] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    demo: bool = False


def _roadworks_near(route: Route, works: list[Roadwork]) -> list[Roadwork]:
    dense = resample(route.coords, 0.1)
    return [w for w in works if min_distance_km(w.location, dense) <= ROADWORK_RADIUS_KM]


def score_route(route: Route, seed: int, params: SearchParams, weights: Weights,
                cfg: Config, http: HttpClient, cache: Optional[Cache],
                providers: list[TrafficProvider], notes: list[str]) -> ScoredRoute:
    """Compute all scores for one route. Failing data sources only add a note."""
    warnings: list[str] = []

    # weather at the time the rider passes each sample point
    targets = [(km, p, params.start_time + timedelta(minutes=route.duration_min * km / route.distance_km))
               for km, p in sample_along(route.coords, WEATHER_STEP_KM)]
    weather_points, weather_source = [], "none"
    if cfg.demo:
        weather_points, weather_source = mock.mock_weather(route, targets, seed), "demo data"
    else:
        try:
            weather_points = GeoSphereClient(http, cache).forecast(targets)
            weather_source = "GeoSphere Austria"
        except DataError as ex:
            notes.append(f"Weather unavailable: {ex}")
    w_score = weather_score(weather_points)
    if w_score is not None and any(p.precip_mm >= 0.1 for p in weather_points):
        warnings.append("Rain expected on this route")

    # roadworks
    try:
        works = fetch_roadworks(route)
    except DataError as ex:
        works = mock.mock_roadworks(route, seed) if cfg.demo else []
        if not cfg.demo:
            note = f"Roadworks: {ex}"
            if note not in notes:
                notes.append(note)
    works = _roadworks_near(route, works)
    warnings += [w.description for w in works]

    # traffic (EVIS.AT -> Google -> estimate)
    info, tnotes = traffic_with_fallback(providers, route, params.start_time)
    for n in tnotes:
        if n not in notes and not cfg.demo:
            notes.append(n)

    curves = curve_score(route.coords, route.elevations, route.main_road_share)
    traffic = traffic_score(info.congestion_factor, len(works))
    score = RouteScore(
        curves=curves, weather=w_score, traffic=traffic,
        overall=overall_score(curves, w_score, traffic, weights),
        traffic_source=info.source + (" (estimated)" if info.estimated else ""),
        weather_source=weather_source, warnings=warnings)
    return ScoredRoute(route=route, score=score, weather_points=weather_points, roadworks=works)


def find_scored_routes(params: SearchParams, weights: Weights, cfg: Config,
                       http: Optional[HttpClient] = None,
                       cache_dir=None) -> SearchResult:
    """Main entry point used by the UI. Never raises for data problems: they become notes."""
    http = http or HttpClient()
    cache = Cache(cache_dir or default_dir() / "cache", ttl_seconds=3600)
    result = SearchResult(demo=cfg.demo)
    if cfg.demo:
        result.notes.append("Demo mode: no ORS_API_KEY set, routes and weather are generated.")
    providers: list[TrafficProvider] = [EvisProvider(cfg.evis_key)]
    if cfg.google_key:
        providers.append(GoogleProvider(cfg.google_key, http))
    providers.append(EstimateProvider())

    ors = None if cfg.demo else OrsClient(cfg.ors_key, http, cache)
    for seed in range(params.n_routes):
        rid, name = f"{params.start.lat:.3f},{params.start.lon:.3f}-{int(params.length_km)}-{seed}", ROUTE_NAMES[seed % 5]
        try:
            route = (mock.mock_route(params.start, params.length_km, seed, rid, name) if ors is None
                     else ors.round_trip(params.start, params.length_km, seed, rid, name))
        except DataError as ex:
            result.notes.append(f"{name}: route not available ({ex})")
            continue
        result.routes.append(score_route(route, seed, params, weights, cfg, http, cache,
                                         providers, result.notes))
    if not result.routes:
        result.notes.append("No routes found. Try another start point or length.")
    result.routes = rank_routes(result.routes)
    return result
