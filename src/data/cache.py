"""Tiny JSON file cache with expiry (keeps us inside API rate limits)."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable, Optional


class Cache:
    """Key = any JSON-serialisable value (the request parameters)."""

    def __init__(self, directory: Path, ttl_seconds: float = 3600,
                 now: Callable[[], float] = time.time) -> None:
        self.directory = Path(directory)
        self.ttl = ttl_seconds
        self._now = now

    def _path(self, key: Any) -> Path:
        digest = hashlib.sha1(json.dumps(key, sort_keys=True, default=str).encode()).hexdigest()
        return self.directory / f"{digest}.json"

    def get(self, key: Any) -> Optional[Any]:
        """Return the cached value or None if missing, expired or unreadable."""
        path = self._path(key)
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
            if self._now() - entry["time"] > self.ttl:
                return None
            return entry["value"]
        except (OSError, ValueError, KeyError):
            return None

    def set(self, key: Any, value: Any) -> None:
        """Store a value. Cache problems never break the app."""
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            self._path(key).write_text(
                json.dumps({"time": self._now(), "value": value}), encoding="utf-8")
        except (OSError, TypeError):
            pass
