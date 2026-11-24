"""Builds every screen with demo data. Catches wrong Flet arguments without opening a window."""
from datetime import datetime

import flet as ft

from data.config import Config
from models.models import LatLon, SearchParams, Settings, Weights
from service import find_scored_routes
from ui.charts import elevation_chart, route_map, score_bar_chart, weather_chart
from ui.detail_view import detail_view
from ui.input_view import InputView, start_time_options
from ui.results_view import results_view


def demo_routes(tmp_path):
    params = SearchParams(LatLon(47.07, 15.44), 90, datetime(2026, 6, 6, 10), 5)
    return find_scored_routes(params, Weights(), Config(), cache_dir=tmp_path).routes


def test_all_views_build(tmp_path):
    routes = demo_routes(tmp_path)
    assert isinstance(results_view(routes, ["note"], lambda sr: None), ft.Column)
    assert results_view([], ["nothing"], lambda sr: None) is not None
    assert score_bar_chart(routes) is not None
    assert route_map(routes) is not None
    sr = routes[0]
    assert elevation_chart(sr) is not None and weather_chart(sr.weather_points) is not None
    noop = lambda e=None: None
    assert detail_view(sr, False, noop, noop, noop) is not None
    assert detail_view(sr, True, noop, noop, noop) is not None


def test_weather_preview_builds():
    from ui.charts import weather_preview
    from models.models import WeatherPoint
    pts = [WeatherPoint(i, datetime(2026, 6, 1, 10 + i), 0, 0, 15 + i, 0.5 if i == 3 else 0, 10 * i)
           for i in range(6)]
    assert weather_preview(pts, "summary") is not None


def test_input_view_reads_values():
    async def search(e):
        pass

    async def lookup(text):
        return []

    view = InputView(Settings(home="Graz"), demo=True, on_search=search, lookup=lookup)
    v = view.read()
    assert v.home == "Graz" and v.start is None and v.n_routes == 4 and v.weights.curves == 1.0
    view.selected = LatLon(47.0, 15.0)
    assert view.read().start == LatLon(47.0, 15.0)
    view.home.value = " "
    try:
        view.read()
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_start_time_options_start_with_now():
    opts = start_time_options(datetime(2026, 6, 1, 8, 30))
    assert opts[0][0].startswith("Now") and opts[1][1] == datetime(2026, 6, 1, 9, 0)
