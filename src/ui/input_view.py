"""Input screen: place search with map, length, start time and weights."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Awaitable, Callable, Optional

import flet as ft

from data.errors import DataError
from logic.weather_score import describe_weather
from models.models import LatLon, Place, Settings, WeatherPoint, Weights
from ui import charts


@dataclass
class InputValues:
    """What the user entered. ``start`` is None if only text was typed (app geocodes it)."""

    home: str
    start: Optional[LatLon]
    length_km: float
    start_time: datetime
    n_routes: int
    weights: Weights


def start_time_options(now: datetime | None = None, hours: int = 48) -> list[tuple[str, datetime]]:
    """'Now' plus the next full hours."""
    now = (now or datetime.now()).replace(second=0, microsecond=0)
    first = now.replace(minute=0) + timedelta(hours=1)
    opts = [(f"Now ({now:%a %H:%M})", now)]
    opts += [(f"{t:%a %d.%m. %H:%M}", t) for t in (first + timedelta(hours=i) for i in range(hours))]
    return opts


class InputView:
    """Builds the form. ``control`` is shown on screen, ``read()`` returns the values.

    ``lookup(text)`` is an async function returning place suggestions (it may raise DataError).
    """

    def __init__(self, settings: Settings, demo: bool,
                 on_search: Callable[[ft.ControlEvent], Awaitable[None]],
                 lookup: Callable[[str], Awaitable[list[Place]]],
                 weather_lookup: Optional[Callable[[LatLon, datetime],
                                                   Awaitable[list[WeatherPoint]]]] = None) -> None:
        self._lookup = lookup
        self._weather_lookup = weather_lookup
        self.selected: Optional[LatLon] = None
        self._times = {t.isoformat(): t for _, t in start_time_options()}

        self.home = ft.TextField(
            label="Where are you? (village, town or address)", value=settings.home, width=520,
            hint_text="e.g. Pöllau, Graz, Hartberg ...", prefix_icon=ft.Icons.PLACE,
            on_submit=self._on_find_place)
        self.find_btn = ft.Button(content="Find place", icon=ft.Icons.SEARCH,
                                  on_click=self._on_find_place)
        self.place_status = ft.Text("Type a place and press Enter - or tap the map.", size=12,
                                    italic=True)
        self.suggestions = ft.Column(spacing=0)
        self.map_box = ft.Container()
        self._set_map(None)
        self.weather_box = ft.Container()
        self._weather_token = 0  # ignore outdated answers if the user changes the place quickly

        self.length_label = ft.Text(f"Loop length: {settings.length_km:.0f} km")
        self.length = ft.Slider(min=30, max=250, divisions=22, value=settings.length_km,
                                label="{value} km", expand=True, on_change=self._length_changed)
        self.start_time = ft.Dropdown(
            label="Start time", width=240, value=next(iter(self._times)),
            on_select=self._refresh_weather,
            options=[ft.DropdownOption(key=t.isoformat(), text=label)
                     for label, t in start_time_options()])
        self.n_routes = ft.Dropdown(
            label="Number of routes", width=160, value=str(settings.n_routes),
            options=[ft.DropdownOption(key=str(n), text=str(n)) for n in (3, 4, 5)])
        self.w_curves = self._weight_slider(settings.weights.curves)
        self.w_weather = self._weight_slider(settings.weights.weather)
        self.w_traffic = self._weight_slider(settings.weights.traffic)
        self.error = ft.Text("", color=ft.Colors.RED_700)
        self.control = ft.Column([
            ft.Text("Which loop is worth riding today?", size=22, weight=ft.FontWeight.BOLD),
            *([ft.Text("Demo mode: no ORS_API_KEY found, routes and weather are generated.",
                       color=ft.Colors.ORANGE_800, italic=True)] if demo else []),
            ft.Row([self.home, self.find_btn], wrap=True),
            self.place_status,
            self.suggestions,
            self.map_box,
            self.weather_box,
            ft.Row([self.length_label, self.length]),
            ft.Row([self.start_time, self.n_routes], wrap=True),
            ft.Text("What matters to you? (0 = ignore, 3 = very important)",
                    weight=ft.FontWeight.W_500),
            self._weight_row("Curves", self.w_curves),
            self._weight_row("Weather", self.w_weather),
            self._weight_row("Traffic", self.w_traffic),
            self.error,
            ft.Button(content="Find routes", icon=ft.Icons.TWO_WHEELER, on_click=on_search,
                      tooltip="Generate loops and rate them"),
        ], spacing=12)

    # ------------------------------------------------------------- place search
    def _set_map(self, point: Optional[LatLon]) -> None:
        self.map_box.content = charts.location_map(point, on_pick=self._on_map_pick)

    async def _choose(self, label: str, point: LatLon) -> None:
        self.selected = point
        self.home.value = label
        self.suggestions.controls = []
        self.place_status.value = f"Start point set: {label}"
        self._set_map(point)
        self.control.update()
        await self._refresh_weather()

    async def _on_map_pick(self, point: LatLon) -> None:
        await self._choose(f"Map point {point.lat:.4f}, {point.lon:.4f}", point)

    def _pick_handler(self, place: Place):
        async def handler(e: ft.ControlEvent) -> None:
            await self._choose(place.label, place.location)
        return handler

    async def _refresh_weather(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Rough weather preview for the chosen start point and start time."""
        if self.selected is None or self._weather_lookup is None:
            return
        self._weather_token += 1
        token = self._weather_token
        self.weather_box.content = ft.Row([ft.ProgressRing(width=18, height=18),
                                           ft.Text("Loading weather preview ...")], spacing=10)
        self.control.update()
        start = self._times.get(self.start_time.value or "", datetime.now())
        try:
            points = await self._weather_lookup(self.selected, start)
            content: ft.Control = (
                charts.weather_preview(points, describe_weather(points))
                if points else ft.Text("No forecast for this place and time.", italic=True))
        except DataError as ex:
            content = ft.Text(f"Weather preview unavailable: {ex}", italic=True,
                              color=ft.Colors.ORANGE_800)
        if token == self._weather_token:  # only show the newest answer
            self.weather_box.content = content
            self.control.update()

    async def _on_find_place(self, e: ft.ControlEvent) -> None:
        text = (self.home.value or "").strip()
        self.error.value = ""
        self.selected = None
        if not text:
            self.place_status.value = "Please enter a place name."
            self.control.update()
            return
        self.place_status.value = "Searching ..."
        self.control.update()
        try:
            places = await self._lookup(text)
        except DataError as ex:
            self.suggestions.controls = []
            self.place_status.value = f"Search failed: {ex}"
            self.control.update()
            return
        if not places:
            self.suggestions.controls = []
            self.place_status.value = f"'{text}' not found in Austria. Check the spelling or tap the map."
            self.control.update()
            return
        if len(places) == 1:
            await self._choose(places[0].label, places[0].location)
            return
        self.place_status.value = "Choose your start point:"
        self.suggestions.controls = [
            ft.ListTile(leading=ft.Icon(ft.Icons.LOCATION_ON), title=ft.Text(p.label),
                        dense=True, on_click=self._pick_handler(p))
            for p in places]
        self.control.update()

    # ------------------------------------------------------------- other inputs
    @staticmethod
    def _weight_slider(value: float) -> ft.Slider:
        return ft.Slider(min=0, max=3, divisions=6, value=value, label="{value}", expand=True)

    @staticmethod
    def _weight_row(name: str, slider: ft.Slider) -> ft.Control:
        return ft.Row([ft.Text(name, width=70), slider])

    def _length_changed(self, e: ft.ControlEvent) -> None:
        self.length_label.value = f"Loop length: {self.length.value:.0f} km"
        self.length_label.update()

    def read(self) -> InputValues:
        """Return the entered values. Raises ValueError with a user-friendly message."""
        home = (self.home.value or "").strip()
        if not home:
            raise ValueError("Please enter where you are (or tap the map).")
        return InputValues(
            home=home, start=self.selected, length_km=float(self.length.value),
            start_time=self._times.get(self.start_time.value or "", datetime.now()),
            n_routes=int(self.n_routes.value or 4),
            weights=Weights(self.w_curves.value, self.w_weather.value, self.w_traffic.value))
