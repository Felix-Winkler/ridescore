"""Map and chart builders (Flet controls). No data fetching and no scoring here."""
from __future__ import annotations

import inspect
import math
from typing import Optional

import flet as ft
import flet_charts as fc
import flet_map as fm

from logic.geo import bounds
from models.models import LatLon, ScoredRoute, WeatherPoint

TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
SCORE_COLORS = {1: "#d73027", 2: "#fc8d59", 3: "#e6b800", 4: "#91cf60", 5: "#1a9850"}
CURVES_COLOR, WEATHER_COLOR, TRAFFIC_COLOR = "#6a3d9a", "#1f78b4", "#ff7f00"
MAX_POINTS = 300


def score_color(score: float) -> str:
    """Colour for a 1..5 score (red = bad, green = good)."""
    return SCORE_COLORS[max(1, min(5, round(score)))]


def _thin(items: list, limit: int = MAX_POINTS) -> list:
    step = max(1, len(items) // limit)
    out = items[::step]
    if items and out[-1] is not items[-1]:
        out.append(items[-1])
    return out


def _ll(p: LatLon) -> fm.MapLatitudeLongitude:
    return fm.MapLatitudeLongitude(p.lat, p.lon)


def _zoom_for(lat_span: float, lon_span: float) -> float:
    """Zoom level so the routes fill a ~900x380 px map (256 px tiles)."""
    span = max(lon_span, lat_span * 1.8, 0.002)
    return max(4.0, min(15.0, math.log2(1265 / span) - 0.3))


def route_map(routes: list[ScoredRoute], selected_id: Optional[str] = None,
              height: int = 380) -> ft.Control:
    """Map with every route coloured by its overall score (selected one drawn thicker)."""
    all_pts = [p for r in routes for p in r.route.coords]
    if not all_pts:
        return ft.Container(height=height)
    min_lat, min_lon, max_lat, max_lon = bounds(all_pts)
    centre = LatLon((min_lat + max_lat) / 2, (min_lon + max_lon) / 2)

    lines = [
        fm.PolylineMarker(
            coordinates=[_ll(p) for p in _thin(r.route.coords)],
            color=score_color(r.score.overall),
            border_color="#222222", border_stroke_width=1.5,
            stroke_width=8 if r.route.id == selected_id else 5)
        for r in routes
    ]
    start = routes[0].route.coords[0]
    markers = [fm.Marker(content=ft.Icon(ft.Icons.TWO_WHEELER, color="#222222", size=30),
                         coordinates=_ll(start))]
    for r in routes:
        for w in r.roadworks:
            markers.append(fm.Marker(
                content=ft.Icon(ft.Icons.CONSTRUCTION, color="#d73027", size=26,
                                tooltip=w.description),
                coordinates=_ll(w.location)))
    return ft.Container(
        height=height, border_radius=8, clip_behavior=ft.ClipBehavior.HARD_EDGE,
        content=fm.Map(
            initial_center=_ll(centre),
            initial_zoom=_zoom_for(max_lat - min_lat, max_lon - min_lon),
            layers=[
                fm.TileLayer(url_template=TILE_URL, user_agent_package_name="at.ridescore.app"),
                fm.PolylineLayer(polylines=lines),
                fm.MarkerLayer(markers=markers),
                fm.RichAttribution(attributions=[
                    fm.TextSourceAttribution(text="OpenStreetMap contributors")]),
            ]))


def location_map(point: Optional[LatLon], on_pick=None, height: int = 280) -> ft.Control:
    """Map to choose the start point. Shows a pin at ``point`` (or Austria if None).

    ``on_pick(LatLon)`` is called when the user taps the map.
    """
    centre = point or LatLon(47.5, 14.0)
    zoom = 13.0 if point else 6.5
    layers = [fm.TileLayer(url_template=TILE_URL, user_agent_package_name="at.ridescore.app")]
    if point:
        layers.append(fm.MarkerLayer(markers=[fm.Marker(
            content=ft.Icon(ft.Icons.LOCATION_ON, color="#d73027", size=40),
            coordinates=_ll(point), alignment=ft.Alignment(0, -0.8))]))
    layers.append(fm.RichAttribution(attributions=[
        fm.TextSourceAttribution(text="OpenStreetMap contributors")]))

    async def tapped(e) -> None:
        if on_pick and e.coordinates is not None:
            result = on_pick(LatLon(e.coordinates.latitude, e.coordinates.longitude))
            if inspect.isawaitable(result):
                await result

    return ft.Container(
        height=height, border_radius=8, clip_behavior=ft.ClipBehavior.HARD_EDGE,
        content=fm.Map(initial_center=_ll(centre), initial_zoom=zoom, layers=layers,
                       on_tap=tapped))


def weather_preview(points: list[WeatherPoint], summary: str, step_h: int = 2) -> ft.Control:
    """Small strip of forecast tiles (time, icon, temperature, rain) plus a summary line."""
    tiles = []
    for p in points[::step_h]:
        raining = p.precip_mm >= 0.1
        icon = ft.Icons.UMBRELLA if raining else (ft.Icons.AIR if p.wind_kmh > 30 else ft.Icons.WB_SUNNY)
        colour = "#1f78b4" if raining else ("#555555" if p.wind_kmh > 30 else "#e6a800")
        tiles.append(ft.Container(
            padding=8, border_radius=8, border=ft.Border.all(1, "#888888"),
            tooltip=f"{p.time.astimezone():%H:%M}: {p.temp_c:.0f} °C, {p.precip_mm:.1f} mm/h, "
                    f"wind {p.wind_kmh:.0f} km/h",
            content=ft.Column([
                ft.Text(f"{p.time.astimezone():%H:%M}", size=12),
                ft.Icon(icon, color=colour, size=26),
                ft.Text(f"{p.temp_c:.0f} °C", weight=ft.FontWeight.BOLD),
                ft.Text(f"{p.precip_mm:.1f} mm" if p.precip_mm >= 0.1 else "dry", size=11),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2, tight=True)))
    return ft.Column([ft.Text(summary, weight=ft.FontWeight.W_500),
                      ft.Row(tiles, wrap=True, spacing=8),
                      ft.Text("Forecast: GeoSphere Austria (CC BY 4.0)", size=11, italic=True)],
                     spacing=6)


def _legend_items(items: list[tuple[str, str]]) -> list[ft.Control]:
    return [ft.Row([ft.Container(width=14, height=14, bgcolor=c, border_radius=3), ft.Text(t)],
                   spacing=6, tight=True) for t, c in items]


def _legend(items: list[tuple[str, str]]) -> ft.Control:
    return ft.Row(_legend_items(items), spacing=16, wrap=True)


def score_legend(label: str = "Route colour = overall score:") -> ft.Control:
    """Colour legend for the map (route colour = overall score), one wrapping row."""
    items = _legend_items([(f"{n}", c) for n, c in SCORE_COLORS.items()])
    return ft.Row([ft.Text(label), *items], spacing=16, wrap=True)


def score_bar_chart(routes: list[ScoredRoute]) -> ft.Control:
    """Grouped bars: curves / weather / traffic per route. Y axis 0..5, with legend."""
    groups = []
    for i, r in enumerate(routes):
        s = r.score
        vals = [("Curves", s.curves, CURVES_COLOR), ("Weather", s.weather, WEATHER_COLOR),
                ("Traffic", s.traffic, TRAFFIC_COLOR)]
        groups.append(fc.BarChartGroup(x=i, rods=[
            fc.BarChartRod(from_y=0, to_y=v or 0, width=16, color=c,
                           tooltip=f"{r.route.name} - {n}: " + (f"{v:.1f}" if v else "n/a"))
            for n, v, c in vals]))
    chart = fc.BarChart(
        groups=groups, min_y=0, max_y=5, height=260, interactive=True,
        horizontal_grid_lines=fc.ChartGridLines(interval=1, color="#cccccc", width=1),
        left_axis=fc.ChartAxis(
            title=ft.Text("Score (1-5)"), title_size=28, label_size=30,
            labels=[fc.ChartAxisLabel(value=v, label=ft.Text(str(v))) for v in range(6)]),
        bottom_axis=fc.ChartAxis(
            title=ft.Text("Route"), title_size=28, label_size=28,
            labels=[fc.ChartAxisLabel(value=i, label=ft.Text(r.route.name))
                    for i, r in enumerate(routes)]))
    return ft.Column([chart, _legend([("Curves", CURVES_COLOR), ("Weather", WEATHER_COLOR),
                                      ("Traffic", TRAFFIC_COLOR)])])


def _ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    if hi <= lo:
        return [lo]
    return [lo + (hi - lo) * i / (n - 1) for i in range(n)]


def line_chart(xs: list[float], ys: list[float], x_title: str, y_title: str,
               color: str, height: int = 220) -> ft.Control:
    """Simple one-series line chart with labelled axes (units are part of the titles)."""
    pts = _thin(list(zip(xs, ys)), 120)
    y_lo, y_hi = min(ys), max(ys)
    pad = max(1.0, (y_hi - y_lo) * 0.1)
    y_lo, y_hi = y_lo - pad, y_hi + pad
    x_hi = max(xs) if xs else 1
    return fc.LineChart(
        height=height, min_x=0, max_x=x_hi, min_y=y_lo, max_y=y_hi, interactive=True,
        data_series=[fc.LineChartData(
            points=[fc.LineChartDataPoint(x, y) for x, y in pts],
            color=color, stroke_width=3, curved=False)],
        horizontal_grid_lines=fc.ChartGridLines(interval=(y_hi - y_lo) / 4, color="#dddddd", width=1),
        left_axis=fc.ChartAxis(
            title=ft.Text(y_title), title_size=28, label_size=44,
            labels=[fc.ChartAxisLabel(value=v, label=ft.Text(f"{v:.0f}")) for v in _ticks(y_lo, y_hi)]),
        bottom_axis=fc.ChartAxis(
            title=ft.Text(x_title), title_size=28, label_size=28,
            labels=[fc.ChartAxisLabel(value=v, label=ft.Text(f"{v:.0f}")) for v in _ticks(0, x_hi)]))


def elevation_chart(sr: ScoredRoute) -> Optional[ft.Control]:
    """Elevation profile (m) along the route (km). None if the route has no elevation."""
    from logic.geo import cumulative_km
    r = sr.route
    if not r.elevations or len(r.elevations) != len(r.coords):
        return None
    return line_chart(cumulative_km(r.coords), r.elevations, "Distance (km)", "Elevation (m)",
                      CURVES_COLOR)


def weather_chart(points: list[WeatherPoint]) -> Optional[ft.Control]:
    """Temperature (deg C) along the route (km). None if there is no forecast."""
    if len(points) < 2:
        return None
    return line_chart([p.km for p in points], [p.temp_c for p in points],
                      "Distance (km)", "Temperature (°C)", WEATHER_COLOR)
