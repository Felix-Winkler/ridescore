"""Common interface of the three traffic sources and the fallback chain."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from data.errors import DataError
from models.models import Route, TrafficInfo


class TrafficProvider(Protocol):
    """A traffic source. Raise DataError / DataUnavailable if it cannot answer."""

    name: str

    def get_traffic(self, route: Route, start_time: datetime) -> TrafficInfo: ...


def traffic_with_fallback(providers: list[TrafficProvider], route: Route,
                          start_time: datetime) -> tuple[TrafficInfo, list[str]]:
    """Try providers in order (EVIS.AT -> Google -> estimate). Returns the result and notes."""
    notes: list[str] = []
    for provider in providers:
        try:
            return provider.get_traffic(route, start_time), notes
        except DataError as ex:
            notes.append(f"{provider.name}: {ex}")
    raise DataError("No traffic provider available.")
