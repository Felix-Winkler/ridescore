"""Configuration from environment variables / .env (keys are never hard-coded)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Config:
    ors_key: str = ""
    google_key: str = ""
    evis_key: str = ""

    @property
    def demo(self) -> bool:
        """Without an OpenRouteService key the app runs on generated demo routes."""
        return not self.ors_key


def load_config() -> Config:
    """Read .env from the project root (if present) and the environment."""
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    return Config(
        ors_key=os.environ.get("ORS_API_KEY", "").strip(),
        google_key=os.environ.get("GOOGLE_API_KEY", "").strip(),
        evis_key=os.environ.get("EVIS_API_KEY", "").strip(),
    )
