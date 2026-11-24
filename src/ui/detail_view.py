"""Detail screen of one route."""
from __future__ import annotations

from typing import Callable

import flet as ft

from models.models import ScoredRoute
from ui import charts
from ui.results_view import score_chip


def detail_view(sr: ScoredRoute, is_favourite: bool,
                on_toggle_favourite: Callable[[ft.ControlEvent], None],
                on_export_gpx: Callable[[ft.ControlEvent], None],
                on_back: Callable[[ft.ControlEvent], None]) -> ft.Control:
    s, r = sr.score, sr.route
    elevation = charts.elevation_chart(sr)
    weather = charts.weather_chart(sr.weather_points)
    rain = [p for p in sr.weather_points if p.precip_mm >= 0.1]
    return ft.Column([
        ft.Row([ft.IconButton(ft.Icons.ARROW_BACK, tooltip="Back", on_click=on_back),
                ft.Text(r.name, size=22, weight=ft.FontWeight.BOLD)]),
        ft.Text(f"{r.distance_km:.0f} km  -  about {r.duration_min / 60:.1f} h  -  "
                f"overall score {s.overall:.1f} / 5"),
        ft.Row([score_chip("Curves", s.curves, ft.Icons.TURN_SLIGHT_RIGHT),
                score_chip("Weather", s.weather, ft.Icons.WB_SUNNY),
                score_chip("Traffic", s.traffic, ft.Icons.DIRECTIONS_CAR)], wrap=True),
        ft.Text(f"Traffic source: {s.traffic_source}  |  Weather source: {s.weather_source}",
                size=12, italic=True),
        *[ft.Row([ft.Icon(ft.Icons.WARNING_AMBER, color=ft.Colors.ORANGE_800),
                  ft.Text(w)], spacing=6) for w in s.warnings],
        ft.Row([
            ft.Button(content="Remove favourite" if is_favourite else "Save as favourite",
                      icon=ft.Icons.FAVORITE if is_favourite else ft.Icons.FAVORITE_BORDER,
                      on_click=on_toggle_favourite),
            ft.OutlinedButton(content="Export GPX", icon=ft.Icons.DOWNLOAD,
                              on_click=on_export_gpx, tooltip="Save the route for a navigation device"),
        ], wrap=True),
        charts.route_map([sr], selected_id=r.id),
        ft.Text("Elevation profile", size=16, weight=ft.FontWeight.W_500),
        elevation or ft.Text("No elevation data for this route.", italic=True),
        ft.Text("Temperature along the route", size=16, weight=ft.FontWeight.W_500),
        weather or ft.Text("No weather data (not stored for favourites).", italic=True),
        *([ft.Text("Rain at km: " + ", ".join(f"{p.km:.0f} ({p.precip_mm:.1f} mm/h)" for p in rain))]
          if rain else []),
    ], spacing=12)
