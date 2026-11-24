"""GPX export (pure string building)."""
from __future__ import annotations

from xml.sax.saxutils import escape

from models.models import Route


def route_to_gpx(route: Route) -> str:
    """Return the route as a GPX 1.1 document."""
    pts = []
    for i, c in enumerate(route.coords):
        ele = ""
        if i < len(route.elevations):
            ele = f"<ele>{route.elevations[i]:.1f}</ele>"
        pts.append(f'      <trkpt lat="{c.lat:.6f}" lon="{c.lon:.6f}">{ele}</trkpt>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.1" creator="RideScore" xmlns="http://www.topografix.com/GPX/1/1">\n'
        f"  <trk>\n    <name>{escape(route.name)}</name>\n    <trkseg>\n"
        + "\n".join(pts)
        + "\n    </trkseg>\n  </trk>\n</gpx>\n"
    )
