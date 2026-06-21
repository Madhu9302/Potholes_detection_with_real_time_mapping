"""
Smart Location Resolution Utilities
Priority: EXIF GPS → GPX track → Manual map → Historical
"""
from __future__ import annotations
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional, Tuple, List, Dict


# ── EXIF GPS Extractor ────────────────────────────────────────────────────────

def _dms_to_decimal(dms, ref: str) -> float:
    """Convert EXIF DMS tuple to decimal degrees."""
    d = float(dms[0])
    m = float(dms[1])
    s = float(dms[2])
    dec = d + m / 60 + s / 3600
    if ref in ("S", "W"):
        dec = -dec
    return dec


def extract_exif_gps(img) -> Tuple[Optional[float], Optional[float]]:
    """
    Extract GPS coordinates from a PIL Image's EXIF data.
    Returns (latitude, longitude) or (None, None).
    """
    try:
        from PIL.ExifTags import TAGS, GPSTAGS
        exif_data = img._getexif()
        if not exif_data:
            return None, None

        # Find GPSInfo tag
        gps_info_raw = None
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "GPSInfo":
                gps_info_raw = value
                break

        if not gps_info_raw:
            return None, None

        gps = {}
        for key, val in gps_info_raw.items():
            name = GPSTAGS.get(key, key)
            gps[name] = val

        if "GPSLatitude" not in gps or "GPSLongitude" not in gps:
            return None, None

        lat = _dms_to_decimal(gps["GPSLatitude"],  gps.get("GPSLatitudeRef",  "N"))
        lon = _dms_to_decimal(gps["GPSLongitude"], gps.get("GPSLongitudeRef", "E"))
        return lat, lon

    except Exception:
        return None, None


# ── GPX Parser ────────────────────────────────────────────────────────────────

_GPX_NS = {"gpx": "http://www.topografix.com/GPX/1/1"}


def parse_gpx(gpx_bytes: bytes) -> List[Dict]:
    """
    Parse a GPX file and return a list of track points:
    [{"lat": float, "lon": float, "time": datetime}, ...]
    Time is UTC-aware.
    """
    points = []
    try:
        root = ET.fromstring(gpx_bytes)
        # Support both <trkpt> and <wpt>
        for tag in ("trkpt", "wpt", "rtept"):
            for pt in root.iter(f"{{{_GPX_NS['gpx']}}}{tag}") or root.iter(tag):
                try:
                    lat = float(pt.attrib["lat"])
                    lon = float(pt.attrib["lon"])
                    # Try namespace-aware, then bare
                    time_el = pt.find(f"{{{_GPX_NS['gpx']}}}time") or pt.find("time")
                    ts = None
                    if time_el is not None and time_el.text:
                        raw = time_el.text.strip().replace("Z", "+00:00")
                        ts = datetime.fromisoformat(raw)
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                    points.append({"lat": lat, "lon": lon, "time": ts})
                except Exception:
                    continue
    except Exception:
        pass
    return points


def match_gpx_to_video_time(
    gpx_points: List[Dict],
    video_start_time: Optional[datetime],
    offset_seconds: float = 0.0,
) -> Optional[Tuple[float, float]]:
    """
    Find the GPX point closest to (video_start_time + offset_seconds).
    Returns (lat, lon) or None.
    """
    if not gpx_points or video_start_time is None:
        return None

    timed = [p for p in gpx_points if p["time"] is not None]
    if not timed:
        # No timestamps — return midpoint of full track
        mid = gpx_points[len(gpx_points) // 2]
        return mid["lat"], mid["lon"]

    target = video_start_time
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)

    import math
    best = min(timed, key=lambda p: abs((p["time"] - target).total_seconds()))
    return best["lat"], best["lon"]


def gpx_midpoint(gpx_points: List[Dict]) -> Optional[Tuple[float, float]]:
    """Return the geographic midpoint of a GPX track."""
    if not gpx_points:
        return None
    lats = [p["lat"] for p in gpx_points]
    lons = [p["lon"] for p in gpx_points]
    return sum(lats) / len(lats), sum(lons) / len(lons)


# ── Location Resolution Result ────────────────────────────────────────────────

class LocationResult:
    """Holds a resolved location with its source type and display label."""

    SOURCE_EXIF     = "EXIF GPS"
    SOURCE_GPX      = "GPX Video"
    SOURCE_MANUAL   = "Manual Location"
    SOURCE_HISTORICAL = "Historical"

    def __init__(self, lat: float, lon: float, source: str):
        self.lat    = lat
        self.lon    = lon
        self.source = source

    @property
    def badge_cls(self) -> str:
        return {
            self.SOURCE_EXIF:       "badge-green",
            self.SOURCE_GPX:        "badge-cyan",
            self.SOURCE_MANUAL:     "badge-indigo",
            self.SOURCE_HISTORICAL: "badge-amber",
        }.get(self.source, "badge-indigo")

    @property
    def icon(self) -> str:
        return {
            self.SOURCE_EXIF:       "📷",
            self.SOURCE_GPX:        "🛰️",
            self.SOURCE_MANUAL:     "📍",
            self.SOURCE_HISTORICAL: "🗂️",
        }.get(self.source, "📍")

    def info_html(self, detected_at: str = "") -> str:
        return f"""
        <div class="stat-card s-time" style="margin-top:10px;">
          <div class="lcd-header">📌 Detection Location Info</div>
          <div style="font-size:13px;line-height:1.9;margin-top:6px;color:#94A3B8;">
            <b style="color:#F0F4FF;">Source:</b>
            <span class="badge {self.badge_cls}" style="margin-left:6px;">{self.icon} {self.source}</span><br>
            <b style="color:#F0F4FF;">Latitude:</b> {self.lat:.6f}<br>
            <b style="color:#F0F4FF;">Longitude:</b> {self.lon:.6f}
            {"<br><b style='color:#F0F4FF;'>Detected:</b> " + detected_at if detected_at else ""}
          </div>
        </div>"""
