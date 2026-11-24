"""Persistent settings and favourites (JSON files in the user's home folder)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from models.models import (ScoredRoute, Settings, scored_route_from_dict,
                           scored_route_to_dict, settings_from_dict, settings_to_dict)


def default_dir() -> Path:
    """Folder for app data. Override with the RIDESCORE_HOME environment variable."""
    return Path(os.environ.get("RIDESCORE_HOME", Path.home() / ".ridescore"))


class Storage:
    """Reads and writes settings.json and favourites.json. Corrupt files are ignored."""

    def __init__(self, directory: Optional[Path] = None) -> None:
        self.directory = Path(directory) if directory else default_dir()

    # -- generic helpers
    def _read(self, name: str, default: Any) -> Any:
        try:
            return json.loads((self.directory / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return default

    def _write(self, name: str, data: Any) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / name).write_text(json.dumps(data, indent=2), encoding="utf-8")

    # -- settings
    def load_settings(self) -> Settings:
        try:
            return settings_from_dict(self._read("settings.json", {}))
        except (ValueError, TypeError, AttributeError):
            return Settings()

    def save_settings(self, settings: Settings) -> None:
        self._write("settings.json", settings_to_dict(settings))

    # -- favourites
    def load_favourites(self) -> list[ScoredRoute]:
        out = []
        for d in self._read("favourites.json", []):
            try:
                out.append(scored_route_from_dict(d))
            except (KeyError, ValueError, TypeError):
                continue  # skip broken entries
        return out

    def save_favourites(self, routes: list[ScoredRoute]) -> None:
        self._write("favourites.json", [scored_route_to_dict(r) for r in routes])

    def add_favourite(self, route: ScoredRoute) -> None:
        favs = [f for f in self.load_favourites() if f.route.id != route.route.id]
        favs.append(route)
        self.save_favourites(favs)

    def remove_favourite(self, route_id: str) -> None:
        self.save_favourites([f for f in self.load_favourites() if f.route.id != route_id])

    def is_favourite(self, route_id: str) -> bool:
        return any(f.route.id == route_id for f in self.load_favourites())
