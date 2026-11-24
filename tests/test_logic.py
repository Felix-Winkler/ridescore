from datetime import datetime

import pytest

from logic.curves import curve_score, curviness_deg_per_km
from logic.geo import angle_diff, haversine_km, resample, sample_along
from logic.gpx import route_to_gpx
from logic.ranking import overall_score, rank_routes, rescore
from logic.scaling import scale_to_score
from logic.traffic_score import estimate_congestion, traffic_score
from logic.weather_score import describe_weather, point_score, weather_score
from models.models import (LatLon, Route, RouteScore, ScoredRoute, Weights,
                           WeatherPoint)
from data.mock import mock_route


def straight(n=200):
    return [LatLon(47.0 + i * 0.0005, 15.0) for i in range(n)]


def zigzag(n=200):
    return [LatLon(47.0 + i * 0.0005, 15.0 + (0.0008 if i % 2 else 0)) for i in range(n)]


def wp(temp=20, rain=0.0, wind=10, km=0):
    return WeatherPoint(km, datetime(2026, 6, 1, 12), 47, 15, temp, rain, wind)


def scored(overall, curves=3.0, rid="x"):
    r = Route(rid, rid, straight(3), [], 1, 1)
    return ScoredRoute(r, RouteScore(curves, 3.0, 3.0, overall))


# ---- geo
def test_haversine_one_degree_latitude():
    assert haversine_km(LatLon(47, 15), LatLon(48, 15)) == pytest.approx(111.2, abs=0.3)


def test_angle_diff_wraps():
    assert angle_diff(350, 10) == pytest.approx(20)
    assert angle_diff(10, 350) == pytest.approx(-20)


def test_resample_spacing():
    pts = resample(straight(), 0.1)
    assert haversine_km(pts[0], pts[1]) == pytest.approx(0.1, abs=0.005)


def test_sample_along_includes_start():
    picks = sample_along(straight(), 5)
    # the test road is ~11 km long -> start + one point per 5 km
    assert picks[0][0] == 0 and len(picks) == 3 and picks[1][0] >= 5


# ---- scaling
def test_scale_both_directions():
    assert scale_to_score(0, 0, 10) == 1 and scale_to_score(10, 0, 10) == 5
    assert scale_to_score(1.6, 1.6, 1.0) == 1 and scale_to_score(1.0, 1.6, 1.0) == 5
    assert scale_to_score(99, 0, 10) == 5


# ---- curves
def test_straight_road_is_not_curvy():
    assert curviness_deg_per_km(straight()) < 5
    assert curve_score(straight(), []) == 1.0


def test_twisty_beats_straight():
    assert curve_score(zigzag(), []) > curve_score(straight(), [])


def test_main_road_penalty_and_hill_bonus():
    z = zigzag()
    base = curve_score(z, [])
    assert curve_score(z, [], main_road_share=1.0) < base
    hills = [i * 5.0 for i in range(len(z))]
    assert curve_score(z, hills) >= base


def test_demo_routes_have_increasing_twistiness():
    scores = [curve_score(r.coords, r.elevations)
              for r in (mock_route(LatLon(47.07, 15.44), 100, s, "i", "n") for s in range(5))]
    assert scores[0] < scores[-1]


# ---- weather
def test_perfect_weather_is_five():
    assert weather_score([wp(), wp()]) == 5.0


def test_rain_is_bad_and_worst_point_counts():
    assert point_score(wp(rain=1.0)) <= 1.5
    mixed = weather_score([wp(), wp(), wp(rain=1.0)])
    assert 1.0 <= mixed < 3.5


def test_cold_and_wind_reduce_score():
    assert point_score(wp(temp=2)) < 5 and point_score(wp(wind=60)) < 5


def test_describe_weather():
    assert describe_weather([]) == "No forecast available."
    dry = describe_weather([wp(temp=14), wp(temp=19, wind=22)])
    assert dry.startswith("Dry") and "14-19" in dry and "22 km/h" in dry
    assert "Rain in 1 of 2" in describe_weather([wp(), wp(rain=1.5)])


def test_no_weather_is_none():
    assert weather_score([]) is None


# ---- traffic
def test_traffic_score_range_and_roadworks():
    assert traffic_score(1.0) == 5 and traffic_score(2.0) == 1
    assert traffic_score(1.0, n_roadworks=2) < traffic_score(1.0)
    assert traffic_score(1.0, n_roadworks=50) >= 1


def test_estimate_rush_hour_worse_than_night():
    rush = estimate_congestion(datetime(2026, 6, 1, 8))  # Monday
    night = estimate_congestion(datetime(2026, 6, 1, 3))
    assert rush > night >= 1.0


# ---- ranking
def test_overall_weighted_and_missing_weather():
    assert overall_score(5, 1, 3, Weights(1, 0, 1)) == 4.0
    assert overall_score(4, None, 2, Weights()) == 3.0
    assert overall_score(4, 2, 2, Weights(0, 0, 0)) == pytest.approx(8 / 3)


def test_rank_orders_and_breaks_ties_by_curves():
    a, b, c = scored(3.0, 2.0, "a"), scored(4.0, 1.0, "b"), scored(3.0, 4.0, "c")
    assert [r.route.id for r in rank_routes([a, b, c])] == ["b", "c", "a"]


def test_rescore_changes_ranking():
    a = ScoredRoute(Route("a", "a", straight(3), [], 1, 1), RouteScore(5, 1, 3, 0))
    b = ScoredRoute(Route("b", "b", straight(3), [], 1, 1), RouteScore(1, 5, 3, 0))
    assert rescore([a, b], Weights(1, 0, 0))[0].route.id == "a"
    assert rescore([a, b], Weights(0, 1, 0))[0].route.id == "b"


# ---- gpx
def test_gpx_contains_points_and_escapes_name():
    r = Route("1", "A & B", [LatLon(47, 15), LatLon(47.1, 15.1)], [500, 510], 1, 1)
    gpx = route_to_gpx(r)
    assert gpx.count("<trkpt") == 2 and "A &amp; B" in gpx and "<ele>510.0</ele>" in gpx
