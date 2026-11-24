"""Shared HTTP helper: timeout, retries with backoff, clear errors."""
from __future__ import annotations

import time
from typing import Any, Callable, Optional

import httpx

from data.errors import DataError

RETRY_STATUS = {429, 500, 502, 503, 504}


class HttpClient:
    """Small wrapper around httpx. Every request has a timeout and up to ``retries`` retries."""

    def __init__(self, timeout: float = 10.0, retries: int = 3, backoff: float = 0.5,
                 transport: Optional[httpx.BaseTransport] = None,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self.retries = retries
        self.backoff = backoff
        self._sleep = sleep
        self._client = httpx.Client(timeout=timeout, transport=transport,
                                    headers={"User-Agent": "RideScore-student-project"})

    def get_json(self, url: str, params: Any = None, headers: Optional[dict] = None) -> Any:
        return self._request("GET", url, params=params, headers=headers)

    def post_json(self, url: str, json: Any, headers: Optional[dict] = None) -> Any:
        return self._request("POST", url, json=json, headers=headers)

    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                resp = self._client.request(method, url, **kwargs)
            except httpx.TransportError as ex:  # timeout, DNS, connection reset ...
                last = ex
            else:
                if resp.status_code in RETRY_STATUS:
                    last = DataError(f"HTTP {resp.status_code} from {url}")
                elif resp.status_code >= 400:
                    raise DataError(f"HTTP {resp.status_code} from {url}: {resp.text[:200]}")
                else:
                    try:
                        return resp.json()
                    except ValueError as ex:
                        raise DataError(f"Invalid JSON from {url}") from ex
            if attempt < self.retries:
                self._sleep(self.backoff * (2 ** attempt))
        raise DataError(f"Request failed after {self.retries + 1} attempts: {last}")
