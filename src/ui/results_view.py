"""Results screen: map, score chart and the ranked list."""
from __future__ import annotations

from typing import Callable, Optional

import flet as ft

from models.models import ScoredRoute
from ui import charts


def score_chip(label: str, value: Optional[float], icon: str) -> ft.Control:
    """Coloured chip. Text and icon carry the meaning, not only the colour."""
    text = "n/a" if value is None else f"{value:.1f}"
    colour = "#cccccc" if value is None else charts.score_color(value)
    return ft.Container(
        content=ft.Row([ft.Icon(icon, size=16, color="#111111"),
                        ft.Text(f"{label} {text}", color="#111111", size=13)], spacing=4,
                       tight=True),
        bgcolor=colour, padding=ft.Padding(8, 4, 8, 4), border_radius=12,
        tooltip=f"{label} score (1 = poor, 5 = excellent)")


def route_card(rank: int, sr: ScoredRoute, on_open: Callable[[ScoredRoute], None]) -> ft.Control:
    s, r = sr.score, sr.route
    return ft.Card(content=ft.Container(
        padding=12, ink=True, on_click=lambda e, sr=sr: on_open(sr),
        tooltip="Open details",
        content=ft.Column([
            ft.Row([
                ft.Text(f"#{rank}  {r.name}", size=18, weight=ft.FontWeight.BOLD),
                ft.Text(f"{r.distance_km:.0f} km  -  {r.duration_min / 60:.1f} h"),
                ft.Container(
                    content=ft.Text(f"Overall {s.overall:.1f}", color="#111111",
                                    weight=ft.FontWeight.BOLD),
                    bgcolor=charts.score_color(s.overall), padding=ft.Padding(10, 4, 10, 4),
                    border_radius=12),
            ], wrap=True, spacing=16),
            ft.Row([score_chip("Curves", s.curves, ft.Icons.TURN_SLIGHT_RIGHT),
                    score_chip("Weather", s.weather, ft.Icons.WB_SUNNY),
                    score_chip("Traffic", s.traffic, ft.Icons.DIRECTIONS_CAR)], wrap=True),
            ft.Text(f"Traffic: {s.traffic_source}  |  Weather: {s.weather_source}",
                    size=12, italic=True),
            *[ft.Row([ft.Icon(ft.Icons.WARNING_AMBER, color=ft.Colors.ORANGE_800, size=18),
                      ft.Text(w)], spacing=6) for w in s.warnings],
        ], spacing=8)))


def results_view(routes: list[ScoredRoute], notes: list[str],
                 on_open: Callable[[ScoredRoute], None],
                 title: str = "Results") -> ft.Control:
    """Ranked list. Shows an empty state when there are no routes."""
    note_controls = [ft.Text(n, color=ft.Colors.ORANGE_800, size=12) for n in notes]
    if not routes:
        return ft.Column([ft.Text(title, size=22, weight=ft.FontWeight.BOLD),
                          ft.Text("No routes to show.", italic=True), *note_controls])
    return ft.Column([
        ft.Text(title, size=22, weight=ft.FontWeight.BOLD),
        *note_controls,
        charts.route_map(routes),
        charts.score_legend(),
        ft.Text("Scores per route", size=16, weight=ft.FontWeight.W_500),
        charts.score_bar_chart(routes),
        ft.Text("Ranking (tap a route for details)", size=16, weight=ft.FontWeight.W_500),
        *[route_card(i + 1, r, on_open) for i, r in enumerate(routes)],
    ], spacing=12)
