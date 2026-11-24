"""Traffic score, roadwork penalty and the offline traffic estimate."""
from __future__ import annotations

from datetime import datetime

from logic.scaling import clamp_score, scale_to_score

FREE_FLOW = 1.0
HEAVY = 1.6
ROADWORK_PENALTY = 0.7
MAX_ROADWORK_PENALTY = 2.0


def traffic_score(congestion_factor: float, n_roadworks: int = 0) -> float:
    """Score 1..5 from a congestion factor (1.0 = free flow) minus a roadwork penalty."""
    base = scale_to_score(congestion_factor, worst=HEAVY, best=FREE_FLOW)
    penalty = min(MAX_ROADWORK_PENALTY, ROADWORK_PENALTY * max(0, n_roadworks))
    return clamp_score(base - penalty)


def estimate_congestion(start_time: datetime, main_road_share: float = 0.0) -> float:
    """Rule-based congestion factor from weekday, hour and road type (fallback source)."""
    hour, weekday = start_time.hour, start_time.weekday()
    if weekday < 5:
        extra = 0.25 if (7 <= hour < 9 or 16 <= hour < 18) else (0.05 if 9 <= hour < 16 else 0.0)
    else:
        extra = 0.2 if 10 <= hour < 17 else 0.05  # weekend leisure traffic
    return FREE_FLOW + extra + 0.3 * max(0.0, min(1.0, main_road_share))
