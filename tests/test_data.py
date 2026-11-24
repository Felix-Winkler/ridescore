from datetime import datetime

import httpx
import pytest

from data.cache import Cache
from data.config import Config
from data.errors import DataError
from data.geocode import geocode, parse_coordinates, search_places
from data.http import HttpClient
from data.routes_ors import parse_route
from data.storage import Storage
from data.traffic_base import traffic_with_fallback
from data.traffic_estimate import EstimateProvider
from data.traffic_evis import EvisProvider
from data.weather_geosphere import GeoSphereClient, parse_forecast, parse_hourly
from models.models import LatLon, Route, RouteScore, ScoredRoute, Settings, Weights
from service import find_scored_routes
from models.models import SearchParams


def client(handler, retries=3):
    return HttpClient(transport=httpx.MockTransport(handler), retries=retries,
                      sleep=lambda s: None)


# ---- http
def test_retries_then_succeeds():
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(503) if len(calls) < 3 else httpx.Response(200, json={"ok": 1})

    assert client(handler).get_json("http://x") == {"ok": 1}
    assert len(calls) == 3


def test_gives_up_after_retries():
    with pytest.raises(DataError):
        client(lambda r: httpx.Response(500), retries=2).get_json("http://x")


def test_client_error_is_not_retried():
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(401, text="no")

    with pytest.raises(DataError):
        client(handler).get_json("http://x")
    assert len(calls) == 1


def test_timeout_becomes_data_error():
    def handler(req):
        raise httpx.ConnectTimeout("slow")

    with pytest.raises(DataError):
        client(handler, retries=1).get_json("http://x")


def test_invalid_json_becomes_data_error():
    with pytest.raises(DataError):
        client(lambda r: httpx.Response(200, text="<html>")).get_json("http://x")


# ---- cache
def test_cache_roundtrip_and_expiry(tmp_path):
    t = [1000.0]
    c = Cache(tmp_path, ttl_seconds=60, now=lambda: t[0])
    assert c.get({"a": 1}) is None
    c.set({"a": 1}, [1, 2])
    assert c.get({"a": 1}) == [1, 2]
    t[0] += 61
    assert c.get({"a": 1}) is None


# ---- storage
def test_settings_and_favourites_persist(tmp_path):
    s = Storage(tmp_path)
    assert s.load_settings() == Settings()
    s.save_settings(Settings(weights=Weights(2, 1, 0.5), home="Graz", length_km=80))
    again = Storage(tmp_path).load_settings()
    assert again.weights.curves == 2 and again.home == "Graz" and again.length_km == 80

    r = Route("r1", "Loop", [LatLon(47, 15), LatLon(47.1, 15.1)], [400, 420], 5, 10)
    sr = ScoredRoute(r, RouteScore(4, None, 3, 3.5, warnings=["x"]))
    s.add_favourite(sr)
    s.add_favourite(sr)  # no duplicates
    favs = s.load_favourites()
    assert len(favs) == 1 and favs[0].score.weather is None and favs[0].route.coords[1].lat == 47.1
    assert s.is_favourite("r1")
    s.remove_favourite("r1")
    assert s.load_favourites() == []


def test_corrupt_files_are_ignored(tmp_path):
    (tmp_path / "settings.json").write_text("{not json")
    (tmp_path / "favourites.json").write_text('[{"broken": 1}]')
    s = Storage(tmp_path)
    assert s.load_settings() == Settings() and s.load_favourites() == []


# ---- geocode
def test_parse_coordinates():
    assert parse_coordinates("47.07, 15.44") == LatLon(47.07, 15.44)
    assert parse_coordinates("Graz") is None
    with pytest.raises(DataError):
        parse_coordinates("200, 15")


def test_search_places_returns_labelled_suggestions():
    payload = [
        {"display_name": "Pöllau, Bezirk Hartberg-Fürstenfeld, Steiermark, 8225, Österreich",
         "lat": "47.3", "lon": "15.9"},
        {"display_name": "Pöllau, Gemeinde X", "lat": "47.0", "lon": "15.0"},
        {"broken": 1},
    ]
    places = search_places("Pöllau", client(lambda r: httpx.Response(200, json=payload)))
    assert len(places) == 2
    assert places[0].label == "Pöllau, Bezirk Hartberg-Fürstenfeld, Steiermark"
    assert places[0].location == LatLon(47.3, 15.9)


def test_search_places_empty_and_coordinates():
    assert search_places("xyzzy", client(lambda r: httpx.Response(200, json=[]))) == []
    p = search_places("47.07, 15.44", client(lambda r: httpx.Response(500)))
    assert p[0].location == LatLon(47.07, 15.44)
    with pytest.raises(DataError):
        search_places("Graz", client(lambda r: httpx.Response(200, json={"oops": 1})))


def test_geocode_not_found_and_found():
    with pytest.raises(DataError):
        geocode("Nowhere", client(lambda r: httpx.Response(200, json=[])))
    ok = client(lambda r: httpx.Response(
        200, json=[{"display_name": "Graz", "lat": "47.07", "lon": "15.44"}]))
    assert geocode("Graz", ok) == LatLon(47.07, 15.44)
    with pytest.raises(DataError):
        geocode("  ", ok)


# ---- ORS parsing
def ors_payload():
    return {"features": [{
        "geometry": {"coordinates": [[15.0, 47.0, 400], [15.1, 47.0, 420], [15.0, 47.0, 400]]},
        "properties": {"summary": {"distance": 20000, "duration": 1800},
                       "extras": {"waytype": {"values": [[0, 1, 1], [1, 2, 3]]}}}}]}


def test_parse_route_ok():
    r = parse_route(ors_payload(), "id", "A")
    assert r.distance_km == 20 and r.duration_min == 30
    assert r.coords[1] == LatLon(47.0, 15.1) and r.elevations == [400, 420, 400]
    assert r.main_road_share == 0.5


def test_parse_route_rejects_bad_data():
    with pytest.raises(DataError):
        parse_route({"features": []}, "id", "A")
    with pytest.raises(DataError):
        parse_route({"nope": 1}, "id", "A")


# ---- GeoSphere parsing
def forecast_payload(n_points=2):
    stamps = ["2026-06-01T10:00+00:00", "2026-06-01T11:00+00:00", "2026-06-01T12:00+00:00"]
    feat = {"properties": {"parameters": {
        "2t": {"data": [18, 19, 20], "unit": "degree Celsius"},
        "tp": {"data": [0, 0, 1.5]},  # precipitation in the last hour (mm)
        "10u": {"data": [3, 3, 3]}, "10v": {"data": [4, 4, 4]}}}}
    return {"timestamps": stamps, "features": [feat] * n_points}


def test_parse_forecast_picks_hour_and_converts():
    when = datetime.fromisoformat("2026-06-01T12:10+00:00")
    targets = [(0.0, LatLon(47, 15), when), (12.0, LatLon(47.1, 15), when)]
    pts = parse_forecast(forecast_payload(), targets)
    assert len(pts) == 2 and pts[0].temp_c == 20
    assert pts[0].precip_mm == 1.5 and pts[0].wind_kmh == pytest.approx(18.0)


def test_parse_forecast_rejects_mismatch():
    when = datetime.fromisoformat("2026-06-01T12:00+00:00")
    with pytest.raises(DataError):
        parse_forecast(forecast_payload(1), [(0, LatLon(47, 15), when)] * 2)
    with pytest.raises(DataError):
        parse_forecast({}, [(0, LatLon(47, 15), when)])


def test_parse_hourly_window_and_values():
    start = datetime.fromisoformat("2026-06-01T10:00+00:00")
    pts = parse_hourly(forecast_payload(1), start, hours=1)
    assert [p.km for p in pts] == [0.0, 1.0]  # 10:00 and 11:00 only
    assert pts[0].temp_c == 18 and pts[1].precip_mm == 0
    with pytest.raises(DataError):
        parse_hourly({"timestamps": ["x"], "features": []}, start, 3)


def test_outdated_dataset_gives_clear_error():
    """The old dataset returned 200 with empty timestamps - that must not look like 'no rain'."""
    empty = {"timestamps": [], "features": [{"properties": {"parameters": {
        k: {"data": []} for k in ("2t", "tp", "10u", "10v")}}}]}
    start = datetime.fromisoformat("2026-06-01T10:00+00:00")
    with pytest.raises(DataError, match="no data"):
        parse_hourly(empty, start, 6)
    with pytest.raises(DataError, match="no data"):
        parse_forecast(empty, [(0, LatLon(47, 15), start)])


def test_geosphere_hourly_uses_one_request_and_cache(tmp_path):
    calls = []

    def handler(req):
        calls.append(str(req.url))
        return httpx.Response(200, json=forecast_payload(1))

    gs = GeoSphereClient(client(handler), Cache(tmp_path))
    start = datetime.fromisoformat("2026-06-01T10:00+00:00")
    assert len(gs.hourly(LatLon(47, 15), start, 2)) == 3
    gs.hourly(LatLon(47, 15), start, 2)
    assert len(calls) == 1 and calls[0].count("lat_lon") == 1


# ---- traffic fallback
def test_fallback_chain_uses_estimate_and_reports_evis():
    r = Route("1", "A", [LatLon(47, 15), LatLon(47.1, 15)], [], 5, 5)
    info, notes = traffic_with_fallback([EvisProvider(), EstimateProvider()], r,
                                        datetime(2026, 6, 1, 8))
    assert info.source == "Estimate" and info.estimated and notes and "EVIS.AT" in notes[0]


# ---- whole pipeline in demo mode (no network)
def test_demo_pipeline_end_to_end(tmp_path):
    params = SearchParams(LatLon(47.07, 15.44), 80, datetime(2026, 6, 6, 10), 4)
    res = find_scored_routes(params, Weights(), Config(), cache_dir=tmp_path)
    assert res.demo and len(res.routes) == 4
    overall = [r.score.overall for r in res.routes]
    assert overall == sorted(overall, reverse=True)
    for r in res.routes:
        assert 1 <= r.score.curves <= 5 and 1 <= r.score.traffic <= 5
        assert r.score.weather is not None and r.weather_points
    assert any(r.score.warnings for r in res.routes)  # demo rain / roadwork
