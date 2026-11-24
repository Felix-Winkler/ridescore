"""Roadworks / closures (ASFINAG Content Portal, EVIS.AT events) - NOT connected yet.

Open points from the brief: which datasets can be used, access, format, licence. ASFINAG only
covers motorways and expressways; B/L roads need the EVIS.AT event reports.
"""
from __future__ import annotations

from data.errors import DataUnavailable
from models.models import Roadwork, Route


def fetch_roadworks(route: Route) -> list[Roadwork]:
    """Return roadworks near the route. Raises DataUnavailable until a dataset is connected."""
    raise DataUnavailable("roadwork data source not connected yet")
