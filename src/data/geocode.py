"""Turn the user's start point text into coordinates."""
from __future__ import annotations

import re

from data.errors import DataError
from data.http import HttpClient
from models.models import LatLon, Place

_COORD = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*[,;]\s*(-?\d+(?:\.\d+)?)\s*$")
NOMINATIM = "https://nominatim.openstreetmap.org/search"


def parse_coordinates(text: str) -> LatLon | None:
    """Parse 'lat, lon'. Returns None if the text is not a coordinate pair."""
    m = _COORD.match(text)
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(2))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise DataError("Coordinates out of range")
    return LatLon(lat, lon)


def _short_label(display_name: str) -> str:
    """'Graz, Steiermark, 8010, Österreich' style label without the country tail."""
    parts = [p.strip() for p in display_name.split(",")]
    return ", ".join(parts[:3]) if len(parts) > 3 else display_name


def search_places(text: str, http: HttpClient, limit: int = 5) -> list[Place]:
    """Place suggestions for a village / town / address (Nominatim, Austria only).

    Also accepts 'lat, lon'. Returns an empty list if nothing was found.
    """
    text = text.strip()
    if not text:
        raise DataError("Please enter a place name.")
    coords = parse_coordinates(text)
    if coords:
        return [Place(f"{coords.lat:.4f}, {coords.lon:.4f}", coords)]
    data = http.get_json(NOMINATIM, params={
        "q": text, "format": "json", "limit": limit, "countrycodes": "at",
        "accept-language": "de"})
    if not isinstance(data, list):
        raise DataError("Unexpected geocoding response.")
    places = []
    for item in data:
        try:
            places.append(Place(_short_label(str(item["display_name"])),
                                LatLon(float(item["lat"]), float(item["lon"]))))
        except (KeyError, ValueError, TypeError):
            continue  # skip malformed entries
    return places


def geocode(text: str, http: HttpClient) -> LatLon:
    """Best match for a place name or 'lat, lon'."""
    places = search_places(text, http, limit=1)
    if not places:
        raise DataError(f"'{text.strip()}' not found in Austria.")
    return places[0].location
