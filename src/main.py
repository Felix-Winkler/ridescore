"""RideScore - starts the Flet app and wires screens, services and storage together."""
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

import flet as ft

from data.cache import Cache
from data.config import Config, load_config
from data.weather_geosphere import GeoSphereClient
from data.errors import DataError
from data.geocode import geocode, search_places
from data.http import HttpClient
from data.storage import Storage
from logic.gpx import route_to_gpx
from models.models import LatLon, Place, ScoredRoute, SearchParams, Settings, WeatherPoint
from service import SearchResult, find_scored_routes
from ui.detail_view import detail_view
from ui.input_view import InputValues, InputView
from ui.results_view import results_view


class RideScoreApp:
    """Screen controller. All real work happens in service/logic/data."""

    def __init__(self, page: ft.Page, config: Config, storage: Storage) -> None:
        self.page = page
        self.config = config
        self.storage = storage
        self.settings: Settings = storage.load_settings()
        self.http = HttpClient()
        self.cache = Cache(storage.directory / "cache", ttl_seconds=3600)
        self.last_result: Optional[SearchResult] = None
        self.body = ft.Column(spacing=12)
        self.input: Optional[InputView] = None

        page.title = "RideScore"
        page.padding = 20
        page.scroll = ft.ScrollMode.AUTO
        page.appbar = ft.AppBar(
            title=ft.Text("RideScore"), center_title=False,
            actions=[
                ft.IconButton(ft.Icons.SEARCH, tooltip="New search", on_click=self.show_input),
                ft.IconButton(ft.Icons.FAVORITE, tooltip="Favourites", on_click=self.show_favourites),
            ])
        page.add(self.body)
        self.show_input()

    # ------------------------------------------------------------- helpers
    def _show(self, *controls: ft.Control) -> None:
        self.body.controls = list(controls)
        self.page.update()

    def _toast(self, message: str) -> None:
        self.page.show_dialog(ft.SnackBar(content=ft.Text(message)))

    # ------------------------------------------------------------- screens
    def show_input(self, e: Optional[ft.ControlEvent] = None) -> None:
        self.input = InputView(self.settings, self.config.demo, self.on_search,
                               self.lookup_places, self.lookup_weather)
        self._show(self.input.control)

    async def lookup_weather(self, point: LatLon, start: datetime) -> list[WeatherPoint]:
        """Rough forecast for the start point (no API key needed, cached for an hour)."""
        client = GeoSphereClient(self.http, self.cache)
        return await asyncio.to_thread(client.hourly, point, start, 12)

    async def lookup_places(self, text: str) -> list[Place]:
        """Place suggestions for the search box (network call in a worker thread)."""
        return await asyncio.to_thread(search_places, text, self.http)

    def show_results(self, e: Optional[ft.ControlEvent] = None) -> None:
        if not self.last_result:
            self.show_input()
            return
        self._show(results_view(self.last_result.routes, self.last_result.notes, self.show_detail))

    def show_favourites(self, e: Optional[ft.ControlEvent] = None) -> None:
        favs = self.storage.load_favourites()
        note = [] if favs else ["No favourites yet. Open a route and tap 'Save as favourite'."]
        self._show(results_view(favs, note, lambda sr: self.show_detail(sr, back=self.show_favourites),
                                title="Favourites"))

    def show_detail(self, sr: ScoredRoute, back=None) -> None:
        back = back or self.show_results
        fav = self.storage.is_favourite(sr.route.id)

        def toggle(e: ft.ControlEvent) -> None:
            if self.storage.is_favourite(sr.route.id):
                self.storage.remove_favourite(sr.route.id)
                self._toast("Removed from favourites")
            else:
                self.storage.add_favourite(sr)
                self._toast("Saved as favourite")
            self.show_detail(sr, back)

        def export(e: ft.ControlEvent) -> None:
            folder = Path.home() / "Downloads"
            folder = folder if folder.exists() else self.storage.directory
            path = folder / f"ridescore_{sr.route.name.replace(' ', '_')}_{int(sr.route.distance_km)}km.gpx"
            try:
                path.write_text(route_to_gpx(sr.route), encoding="utf-8")
                self._toast(f"GPX saved: {path}")
            except OSError as ex:
                self._toast(f"Could not save GPX: {ex}")

        self._show(detail_view(sr, fav, toggle, export, lambda e: back()))

    # ------------------------------------------------------------- actions
    async def on_search(self, e: ft.ControlEvent) -> None:
        assert self.input is not None
        try:
            values = self.input.read()
        except ValueError as ex:
            self.input.error.value = str(ex)
            self.page.update()
            return
        self.input.error.value = ""
        self.settings = Settings(weights=values.weights, home=values.home,
                                 length_km=values.length_km, n_routes=values.n_routes)
        try:
            self.storage.save_settings(self.settings)
        except OSError:
            pass  # settings are a convenience, never fatal

        self._show(ft.Row([ft.ProgressRing(), ft.Text("Finding and rating routes ...")],
                          spacing=16))
        try:
            result = await asyncio.to_thread(self._search, values)
        except DataError as ex:
            self.show_input()
            assert self.input is not None
            self.input.error.value = str(ex)
            self.page.update()
            return
        self.last_result = result
        self.show_results()

    def _search(self, values: InputValues) -> SearchResult:
        """Runs in a worker thread (blocking network calls)."""
        start = values.start or geocode(values.home, self.http)
        params = SearchParams(start, values.length_km, values.start_time, values.n_routes)
        return find_scored_routes(params, values.weights, self.config, self.http)


def main(page: ft.Page) -> None:
    RideScoreApp(page, load_config(), Storage())


if __name__ == "__main__":
    ft.run(main)
