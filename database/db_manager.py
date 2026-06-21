import sqlite3
import hashlib
import os
import math
from datetime import datetime
from typing import Optional, Dict, List, Tuple

DB_PATH = os.path.join(os.path.dirname(__file__), "pothole_system.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    return salt.hex() + ":" + hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000).hex()

def verify_password(password: str, hashed_password: str) -> bool:
    try:
        salt_hex, key_hex = hashed_password.split(':')
        salt = bytes.fromhex(salt_hex)
        new_key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return new_key == bytes.fromhex(key_hex)
    except Exception:
        return False

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS detections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        file_type TEXT NOT NULL,
        potholes_count INTEGER DEFAULT 0,
        detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS pothole_locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        latitude  REAL NOT NULL,
        longitude REAL NOT NULL,
        confidence REAL NOT NULL DEFAULT 0.0,
        severity  TEXT NOT NULL DEFAULT 'Low',
        source_type TEXT NOT NULL DEFAULT 'Historical',
        status TEXT NOT NULL DEFAULT 'Active',
        remarks TEXT DEFAULT '',
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    # Migrations: add missing columns
    cols = [row[1] for row in c.execute("PRAGMA table_info(pothole_locations)").fetchall()]
    if "source_type" not in cols:
        c.execute("ALTER TABLE pothole_locations ADD COLUMN source_type TEXT NOT NULL DEFAULT 'Historical'")
    if "status" not in cols:
        c.execute("ALTER TABLE pothole_locations ADD COLUMN status TEXT NOT NULL DEFAULT 'Active'")
    if "remarks" not in cols:
        c.execute("ALTER TABLE pothole_locations ADD COLUMN remarks TEXT DEFAULT ''")

    conn.commit()

    c.execute("SELECT COUNT(*) as count FROM users")
    if c.fetchone()["count"] == 0:
        try:
            c.execute("INSERT INTO users (username, email, password_hash) VALUES (?,?,?)",
                      ("admin", "admin@potholesystem.com", hash_password("admin123")))
            aid = c.lastrowid
            for fn, ft, cnt, dt in [
                ("nh8_pothole_1.jpg","image",3,"2026-06-08 10:12:00"),
                ("expressway_scan_2.mp4","video",12,"2026-06-09 14:25:00"),
                ("link_road_pothole.png","image",1,"2026-06-10 09:05:00"),
                ("city_drive_heavy.mp4","video",24,"2026-06-11 17:40:00"),
                ("sector_12_street_4.jpg","image",0,"2026-06-12 11:15:00"),
                ("highway_bypass.mp4","video",8,"2026-06-13 08:30:00"),
            ]:
                c.execute("INSERT INTO detections (user_id,filename,file_type,potholes_count,detected_at) VALUES (?,?,?,?,?)",
                          (aid, fn, ft, cnt, dt))
        except sqlite3.IntegrityError:
            pass

    # Seed historical potholes if map is empty
    c.execute("SELECT COUNT(*) as cnt FROM pothole_locations")
    if c.fetchone()["cnt"] == 0:
        seed = [
            # Indore city cluster
            (22.7196, 75.8577, 0.91, "High",   "Historical",      "2026-06-01 08:00:00"),
            (22.7210, 75.8600, 0.76, "High",   "Historical",      "2026-06-02 09:30:00"),
            (22.7180, 75.8550, 0.62, "Medium", "Historical",      "2026-06-03 11:00:00"),
            (22.7225, 75.8620, 0.55, "Medium", "Historical",      "2026-06-04 14:20:00"),
            (22.7165, 75.8530, 0.44, "Low",    "Historical",      "2026-06-05 16:10:00"),
            (22.7240, 75.8640, 0.38, "Low",    "Historical",      "2026-06-06 10:45:00"),
            (22.7195, 75.8590, 0.88, "High",   "Image Detection", "2026-06-07 12:00:00"),
            (22.7205, 75.8610, 0.72, "Medium", "Video Detection", "2026-06-08 15:30:00"),
            # NH-46 Indore outskirts → Dewas
            (22.7650, 75.9100, 0.88, "High",   "Historical",      "2026-06-10 06:00:00"),
            (22.7890, 75.9380, 0.74, "High",   "Historical",      "2026-06-10 06:15:00"),
            (22.8012, 75.9423, 0.85, "High",   "Historical",      "2026-06-09 07:00:00"),
            (22.8800, 76.0200, 0.73, "High",   "Historical",      "2026-06-09 07:30:00"),
            # Dewas area
            (22.9500, 76.1050, 0.61, "Medium", "Historical",      "2026-06-09 08:00:00"),
            (22.9634, 76.0530, 0.82, "High",   "Historical",      "2026-06-10 07:00:00"),
            (22.9700, 76.0650, 0.65, "Medium", "Historical",      "2026-06-10 07:10:00"),
            (22.9820, 76.0800, 0.51, "Medium", "Historical",      "2026-06-10 07:20:00"),
            # Dewas → Sehore
            (23.0310, 76.2180, 0.55, "Medium", "Historical",      "2026-06-09 08:30:00"),
            (23.0800, 76.2000, 0.70, "High",   "Historical",      "2026-06-10 08:00:00"),
            (23.1100, 76.3300, 0.48, "Low",    "Historical",      "2026-06-09 09:00:00"),
            (23.1200, 76.2500, 0.55, "Medium", "Historical",      "2026-06-10 08:20:00"),
            (23.1600, 76.3100, 0.42, "Low",    "Historical",      "2026-06-10 08:40:00"),
            # Sehore area
            (23.1950, 76.4450, 0.82, "High",   "Historical",      "2026-06-09 09:30:00"),
            (23.2000, 76.3600, 0.78, "High",   "Historical",      "2026-06-10 09:00:00"),
            (23.2100, 76.3750, 0.60, "Medium", "Historical",      "2026-06-10 09:10:00"),
            (23.2700, 76.5500, 0.67, "Medium", "Historical",      "2026-06-09 10:00:00"),
            # Sehore → Bhopal outskirts
            (23.2900, 76.5000, 0.85, "High",   "Historical",      "2026-06-10 09:30:00"),
            (23.3200, 76.5600, 0.67, "Medium", "Historical",      "2026-06-10 09:45:00"),
            (23.3500, 76.6600, 0.44, "Low",    "Historical",      "2026-06-09 10:30:00"),
            (23.3700, 76.6200, 0.50, "Medium", "Historical",      "2026-06-10 10:00:00"),
            (23.4200, 76.7700, 0.79, "High",   "Historical",      "2026-06-09 11:00:00"),
            (23.4500, 76.7100, 0.73, "High",   "Historical",      "2026-06-10 10:20:00"),
            (23.5000, 76.8900, 0.58, "Medium", "Historical",      "2026-06-09 11:30:00"),
            (23.5200, 76.8200, 0.44, "Low",    "Historical",      "2026-06-10 10:40:00"),
        ]
        for lat, lon, conf, sev, src, ts in seed:
            c.execute("INSERT INTO pothole_locations (latitude,longitude,confidence,severity,source_type,timestamp) VALUES (?,?,?,?,?,?)",
                      (lat, lon, conf, sev, src, ts))

    conn.commit()
    conn.close()

def register_user(username: str, email: str, password: str) -> Tuple[bool, Optional[str]]:
    if not username or not email or not password:
        return False, "All fields are required."
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=? OR email=?", (username, email))
    if c.fetchone():
        conn.close()
        return False, "Username or Email already registered."
    try:
        c.execute("INSERT INTO users (username,email,password_hash) VALUES (?,?,?)",
                  (username, email, hash_password(password)))
        conn.commit()
        return True, None
    except Exception as e:
        return False, f"Database error: {e}"
    finally:
        conn.close()

def authenticate_user(username: str, password: str) -> Optional[Dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id,username,email,password_hash FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    if row is None:
        return None
    user = dict(row)
    if verify_password(password, user.pop("password_hash")):
        return user
    return None

def add_detection(user_id: int, filename: str, file_type: str, potholes_count: int) -> bool:
    conn = get_connection()
    try:
        conn.execute("INSERT INTO detections (user_id,filename,file_type,potholes_count) VALUES (?,?,?,?)",
                     (user_id, filename, file_type, potholes_count))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

def get_user_detections(user_id: int) -> List[Dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id,filename,file_type,potholes_count,detected_at FROM detections WHERE user_id=? ORDER BY detected_at DESC",
        (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_detection_stats(user_id: int) -> Dict:
    conn = get_connection()
    c = conn.cursor()
    def q(sql, *args):
        c.execute(sql, args)
        return list(c.fetchone())[0] or 0
    total = q("SELECT COUNT(*) FROM detections WHERE user_id=?", user_id)
    imgs  = q("SELECT COUNT(*) FROM detections WHERE user_id=? AND file_type='image'", user_id)
    vids  = q("SELECT COUNT(*) FROM detections WHERE user_id=? AND file_type='video'", user_id)
    phs   = q("SELECT SUM(potholes_count) FROM detections WHERE user_id=?", user_id)
    conn.close()
    return {
        "total_detections": total, "image_detections": imgs,
        "video_detections": vids, "total_potholes": phs,
        "avg_potholes": round(phs / total, 1) if total else 0.0,
    }

# ── Pothole Locations ─────────────────────────────────────────────────────────

def add_pothole_location(latitude: float, longitude: float, confidence: float,
                          severity: str, source_type: str = "Historical") -> bool:
    if severity not in ("Low","Medium","High"):
        severity = "Low"
    valid_sources = ("Historical","Image Detection","Video Detection","Live Camera")
    if source_type not in valid_sources:
        source_type = "Historical"
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO pothole_locations (latitude,longitude,confidence,severity,source_type) VALUES (?,?,?,?,?)",
            (latitude, longitude, confidence, severity, source_type))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

def get_all_potholes() -> List[Dict]:
    """Returns ALL potholes (Active + Resolved) for management page."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id,latitude,longitude,confidence,severity,source_type,status,remarks,timestamp "
        "FROM pothole_locations ORDER BY timestamp DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_active_potholes() -> List[Dict]:
    """Returns only Active potholes — for map and route planner."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id,latitude,longitude,confidence,severity,source_type,status,timestamp "
        "FROM pothole_locations WHERE status='Active' ORDER BY timestamp DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def set_pothole_status(pothole_id: int, status: str, remarks: str = "") -> bool:
    """Set status to 'Active' or 'Resolved' with optional remarks."""
    if status not in ("Active", "Resolved"):
        return False
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE pothole_locations SET status=?, remarks=? WHERE id=?",
            (status, remarks, pothole_id))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

def get_pothole_map_stats() -> Dict:
    conn = get_connection()
    rows = conn.execute("SELECT severity, source_type, status FROM pothole_locations").fetchall()
    conn.close()
    total      = len(rows)
    high       = sum(1 for r in rows if r["severity"] == "High")
    medium     = sum(1 for r in rows if r["severity"] == "Medium")
    low        = sum(1 for r in rows if r["severity"] == "Low")
    historical = sum(1 for r in rows if r["source_type"] == "Historical")
    live       = total - historical
    active     = sum(1 for r in rows if r["status"] == "Active")
    resolved   = total - active
    rate       = round(resolved / total * 100, 1) if total else 0.0
    conn2 = get_connection()
    last_row = conn2.execute(
        "SELECT timestamp FROM pothole_locations ORDER BY timestamp DESC LIMIT 1").fetchone()
    conn2.close()
    last_ts = last_row["timestamp"] if last_row else None
    return {"total": total, "high": high, "medium": medium, "low": low,
            "historical": historical, "live": live, "active": active,
            "resolved": resolved, "resolution_rate": rate, "last_ts": last_ts}

# ── Geometry helpers ──────────────────────────────────────────────────────────

def _haversine_m(lat1, lon1, lat2, lon2):
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2-lat1); dlambda = math.radians(lon2-lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def _point_to_segment_dist_m(p_lat,p_lon,a_lat,a_lon,b_lat,b_lon):
    lat_ref = (a_lat+b_lat+p_lat)/3.0
    cos_lat = math.cos(math.radians(lat_ref))
    mplat = 110_540.0; mplon = 111_320.0*cos_lat
    bx=(b_lon-a_lon)*mplon; by=(b_lat-a_lat)*mplat
    px=(p_lon-a_lon)*mplon; py=(p_lat-a_lat)*mplat
    seg_sq = bx*bx + by*by
    if seg_sq < 1e-10:
        return math.hypot(px, py)
    t = max(0.0, min(1.0, (px*bx+py*by)/seg_sq))
    return math.hypot(px-t*bx, py-t*by)

def _min_dist_to_route(ph_lat, ph_lon, route_coords):
    if not route_coords: return float("inf")
    n = len(route_coords)
    if n == 1:
        return _haversine_m(ph_lat, ph_lon, route_coords[0][0], route_coords[0][1])
    min_d = float("inf")
    for i in range(n-1):
        a, b = route_coords[i], route_coords[i+1]
        d = _point_to_segment_dist_m(ph_lat, ph_lon, a[0], a[1], b[0], b[1])
        if d < min_d:
            min_d = d
            if min_d == 0.0: break
    return min_d

def annotate_potholes_with_distances(route_coords, radius_m=30.0):
    """Uses only ACTIVE potholes for route scoring."""
    all_potholes = get_active_potholes()
    if not all_potholes: return []
    return [{**ph, "min_dist_m": round(_min_dist_to_route(ph["latitude"],ph["longitude"],route_coords),1),
             "matched": _min_dist_to_route(ph["latitude"],ph["longitude"],route_coords) <= radius_m}
            for ph in all_potholes]

def get_potholes_near_route(route_coords, radius_m=30.0):
    return [ph for ph in annotate_potholes_with_distances(route_coords, radius_m) if ph["matched"]]

_SEVERITY_WEIGHT = {"High": 5, "Medium": 3, "Low": 1}

def score_route(potholes_on_route: List[Dict]) -> Dict:
    counts = {"High": 0, "Medium": 0, "Low": 0}
    for ph in potholes_on_route:
        sev = ph.get("severity","Low")
        if sev in counts: counts[sev] += 1
    total = sum(counts[s]*_SEVERITY_WEIGHT[s] for s in counts)
    return {"high": counts["High"], "medium": counts["Medium"], "low": counts["Low"], "total": total}
