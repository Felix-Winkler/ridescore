"""EVIS.AT traffic state (first choice, NOT connected yet).

Open points from the project brief: access/registration at mobilitydata.gv.at, data format
(probably DATEX II XML), coverage of B/L roads, licence. Until that is clarified this provider
reports "unavailable" so the fallback chain continues with Google or the estimate.

TODO once access exists: download the "Verkehrslage EVIS.AT" feed, parse the sections and
match them to the route (nearest section within a tolerance radius), then return
TrafficInfo(factor, source="EVIS.AT").
"""
from __future__ import annotations

from datetime import datetime

from data.errors import DataUnavailable
from models.models import Route, TrafficInfo


class EvisProvider:
    name = "EVIS.AT"

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key

    def get_traffic(self, route: Route, start_time: datetime) -> TrafficInfo:
        raise DataUnavailable("not connected yet (access/format still to be clarified)")
