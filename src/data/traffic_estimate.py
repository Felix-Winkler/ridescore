"""Always-available traffic estimate (weekday, hour, road type)."""
from __future__ import annotations

from datetime import datetime

from logic.traffic_score import estimate_congestion
from models.models import Route, TrafficInfo


class EstimateProvider:
    name = "Estimate"

    def get_traffic(self, route: Route, start_time: datetime) -> TrafficInfo:
        return TrafficInfo(estimate_congestion(start_time, route.main_road_share),
                           source="Estimate", estimated=True)
