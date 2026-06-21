import streamlit as st
import os
import folium
from streamlit_folium import st_folium
import requests
import polyline as pl_lib
import math
import time
from database import db_manager
from utils.sidebar import render_sidebar

if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first."); st.stop()

try:
    with open("assets/style.css", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    pass

render_sidebar()
db_manager.init_db()

st.markdown("""
<div class="page-header animate-in">
  <h1><span class="gradient-text">Smart Route Planner</span></h1>
  <p class="page-subtitle">Real-world routes scored against pothole hazards with segment-level risk analysis.</p>
</div>""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<div class="sidebar-brand"><div class="brand-name">Route Settings</div></div>', unsafe_allow_html=True)
    radius_m   = st.slider("Pothole corridor radius (m)", 10, 500, 100, step=10)
    st.markdown("""
    <div style="font-size:12px;color:#64748B;margin-top:8px;line-height:1.7;">
    <b style="color:#64748B;">Risk Formula:</b><br>
    High × 5 | Medium × 3 | Low × 1<br>
    Comfort = 100 − norm(Risk)
    </div>""", unsafe_allow_html=True)
    show_debug = False

# ── Constants ──────────────────────────────────────────────────────────────────
_SEV_COLOR  = {"High": "#EF4444", "Medium": "#F59E0B", "Low": "#10B981"}
_SEV_FOLIUM = {"High": "red",     "Medium": "orange",  "Low": "green"}
_SEV_EMOJI  = {"High": "",      "Medium": "",      "Low": ""}
_SEV_WEIGHT = {"High": 5,         "Medium": 3,          "Low": 1}
_RCOLS      = ["#4F46E5", "#F97316", "#EC4899"]

# ── Geocode + Route helpers ────────────────────────────────────────────────────
import json

GEO_CACHE_FILE = "database/geocode_cache.json"

def load_geocode_cache():
    if os.path.exists(GEO_CACHE_FILE):
        try:
            with open(GEO_CACHE_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_geocode_cache(cache):
    try:
        os.makedirs("database", exist_ok=True)
        with open(GEO_CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except:
        pass

def geocode(place):
    place_key = place.lower().strip()
    cache = load_geocode_cache()
    
    # Handle small city names to improve reliability
    search_query = place
    if "," not in place:
        small_cities = ["rau", "mhow", "vijay nagar", "dewas", "ujjain", "ashta", "sehore", "indore", "bhopal"]
        if any(c in place_key for c in small_cities):
            search_query = f"{place}, Madhya Pradesh, India"
    
    # 1. Check persistent cache
    if place_key in cache:
        return cache[place_key]["lat"], cache[place_key]["lon"], cache[place_key]["name"], "Cache"
        
    # 2. Call Nominatim with exponential backoff
    max_retries = 3
    for attempt in range(max_retries):
        try:
            time.sleep(1.5 * (2 ** attempt))  # Exponential backoff
            r = requests.get("https://nominatim.openstreetmap.org/search",
                             params={"q": search_query, "format": "json", "limit": 1},
                             headers={"User-Agent": f"PotholeAI-RoutePlanner/5.{attempt}"}, timeout=10)
            
            if r.status_code == 429:
                continue # Retry
                
            r.raise_for_status()
            data = r.json()
            if not data: raise ValueError(f"Location could not be resolved")
            
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])
            name = data[0]["display_name"]
            
            cache[place_key] = {"lat": lat, "lon": lon, "name": name}
            save_geocode_cache(cache)
            return lat, lon, name, "Nominatim"
            
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise ValueError(f"Location could not be resolved (Network Error: {e})")
        except ValueError as e:
            raise e

    raise ValueError("Location could not be resolved (Too Many Requests)")

@st.cache_data(show_spinner=False, ttl=86400)
def reverse_geocode_short(lat, lon):
    """Return a short locality name for a coordinate (district/city level)."""
    try:
        time.sleep(1.2)  # Prevent Nominatim 429 Too Many Requests
        r = requests.get("https://nominatim.openstreetmap.org/reverse",
                         params={"lat": lat, "lon": lon, "format": "json", "zoom": 10},
                         headers={"User-Agent": "PotholeAI-RoutePlanner/4.0"}, timeout=6)
        if r.status_code == 200:
            addr = r.json().get("address", {})
            # Prefer: city > town > county > state_district
            for k in ("city", "town", "county", "state_district"):
                v = addr.get(k)
                if v: return v
    except Exception:
        pass
    return f"{lat:.3f},{lon:.3f}"

def get_osrm_routes(slat, slon, dlat, dlon):
    url = (f"http://router.project-osrm.org/route/v1/driving/"
           f"{slon},{slat};{dlon},{dlat}?overview=full&geometries=polyline&alternatives=true")
    r = requests.get(url, timeout=25); r.raise_for_status()
    data = r.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError(f"OSRM error: {data.get('code')}")
    return [{"coords":   [[lt, ln] for lt, ln in pl_lib.decode(rt["geometry"])],
             "distance_km":  round(rt["distance"] / 1000, 1),
             "duration_min": round(rt["duration"] / 60)}
            for rt in data["routes"]]

# ── Geometry ───────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False, ttl=86400)
def get_road_name(lat_rnd, lon_rnd):
    # Reverse geocode with zoom level 14 (suburb/road) for better road names
    try:
        time.sleep(1.2)  # Prevent Nominatim 429 Too Many Requests
        r = requests.get("https://nominatim.openstreetmap.org/reverse",
                         params={"lat": lat_rnd, "lon": lon_rnd, "format": "json", "zoom": 14},
                         headers={"User-Agent": "PotholeAI-Corridor/1.0"}, timeout=6)
        if r.status_code == 200:
            addr = r.json().get("address", {})
            return addr.get("road") or addr.get("suburb") or addr.get("village") or addr.get("town") or addr.get("city") or f"{lat_rnd:.3f},{lon_rnd:.3f}"
        else:
            return f"{lat_rnd:.3f},{lon_rnd:.3f}"
    except:
        return f"{lat_rnd:.3f},{lon_rnd:.3f}"

def get_road_name_cached(lat, lon):
    # Round heavily to increase cache hits and reduce API calls
    return get_road_name(round(lat * 50) / 50, round(lon * 50) / 50)

def get_condition(score):
    if score == 0: return "Excellent", "#10B981"
    if score <= 2: return "Good", "#84CC16"
    if score <= 5: return "Moderate", "#F59E0B"
    if score <= 10: return "Poor", "#F97316"
    return "Critical", "#EF4444"

def _haversine_m(lat1, lon1, lat2, lon2):
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin(math.radians(lat2-lat1)/2)**2
         + math.cos(p1)*math.cos(p2)*math.sin(math.radians(lon2-lon1)/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def _pt_seg_dist_m(p_lat, p_lon, a_lat, a_lon, b_lat, b_lon):
    cos_lat = math.cos(math.radians((a_lat+b_lat+p_lat)/3.0))
    mplat = 110_540.0; mplon = 111_320.0 * cos_lat
    bx = (b_lon-a_lon)*mplon; by = (b_lat-a_lat)*mplat
    px = (p_lon-a_lon)*mplon; py = (p_lat-a_lat)*mplat
    ss = bx*bx + by*by
    if ss < 1e-10: return math.hypot(px, py)
    t = max(0.0, min(1.0, (px*bx+py*by)/ss))
    return math.hypot(px-t*bx, py-t*by)

def min_dist_to_route(ph_lat, ph_lon, coords):
    if not coords: return float("inf")
    if len(coords) == 1:
        return _haversine_m(ph_lat, ph_lon, coords[0][0], coords[0][1])
    return min(_pt_seg_dist_m(ph_lat, ph_lon, coords[i][0], coords[i][1],
                               coords[i+1][0], coords[i+1][1])
               for i in range(len(coords)-1))

def nearest_segment_idx(ph_lat, ph_lon, coords):
    """Return index of route segment nearest to pothole."""
    best_i, best_d = 0, float("inf")
    for i in range(len(coords)-1):
        d = _pt_seg_dist_m(ph_lat, ph_lon, coords[i][0], coords[i][1],
                            coords[i+1][0], coords[i+1][1])
        if d < best_d:
            best_d = d; best_i = i
    return best_i

# ── Core scoring ───────────────────────────────────────────────────────────────
def analyse_route(route_coords, all_potholes, radius_m):
    """
    For each pothole, compute distance to this route.
    Returns annotated list of matched potholes with segment index.
    """
    matched = []
    for ph in all_potholes:
        d = min_dist_to_route(ph["latitude"], ph["longitude"], route_coords)
        if d <= radius_m:
            seg_i = nearest_segment_idx(ph["latitude"], ph["longitude"], route_coords)
            # midpoint of that segment → for place name lookup
            mid_lat = (route_coords[seg_i][0] + route_coords[min(seg_i+1, len(route_coords)-1)][0]) / 2
            mid_lon = (route_coords[seg_i][1] + route_coords[min(seg_i+1, len(route_coords)-1)][1]) / 2
            matched.append({**ph, "dist_m": round(d, 1), "seg_i": seg_i,
                             "seg_lat": mid_lat, "seg_lon": mid_lon})
    return matched

def score_potholes(matched):
    counts = {"High": 0, "Medium": 0, "Low": 0}
    for ph in matched:
        sev = ph.get("severity", "Low")
        if sev in counts: counts[sev] += 1
    total = sum(counts[s] * _SEV_WEIGHT[s] for s in counts)
    return {"high": counts["High"], "medium": counts["Medium"],
            "low": counts["Low"], "total": total}

def comfort_index(score_total, max_score):
    if max_score == 0: return 100
    return round(max(0, 100 - (score_total / max_score * 100)))

# ── Segment danger bands ───────────────────────────────────────────────────────
def build_corridor_segments(route_coords, matched_potholes, radius_m):
    """
    Divide the route into continuous 5km structural segments.
    Evaluate the condition of each segment (Excellent -> Critical).
    """
    segments = []
    seg_start = 0
    dist_accum = 0.0
    
    for i in range(1, len(route_coords)):
        lat1, lon1 = route_coords[i-1]
        lat2, lon2 = route_coords[i]
        dist_accum += _haversine_m(lat1, lon1, lat2, lon2)
        
        # Create a segment every 5km or at the end of the route
        if dist_accum >= 5000 or i == len(route_coords) - 1:
            seg_slice = route_coords[seg_start:i+1]
            
            highs = mediums = lows = 0
            for ph in matched_potholes:
                # If pothole nearest segment is within this chunk
                if seg_start <= ph["seg_i"] <= i:
                    sev = ph.get("severity", "Low")
                    if sev == "High": highs += 1
                    elif sev == "Medium": mediums += 1
                    else: lows += 1
            
            score = (highs * 5) + (mediums * 3) + lows
            cond_str, cond_col = get_condition(score)
            
            segments.append({
                "coords": seg_slice,
                "high": highs, "medium": mediums, "low": lows,
                "score": score,
                "condition": cond_str,
                "color": cond_col,
                "mid_idx": seg_start + len(seg_slice)//2
            })
            
            seg_start = i
            dist_accum = 0.0
            
    return segments

# ── Route explanation generator ───────────────────────────────────────────────
def build_explanation(matched, label):
    """
    Group potholes by reverse-geocoded locality and produce a
    human-readable explanation string.
    Reverse-geocode only the first 6 distinct locations to save API calls.
    """
    if not matched:
        return f"✅ {label} is clear — no potholes detected within the route corridor."

    # Cluster potholes that are within 5 km of each other into locality groups
    groups = {}   # place_name → list of potholes
    looked_up = {}  # (round_lat, round_lon) → place_name cache

    for ph in matched:
        # Use ~0.05° grid (~5 km) for grouping
        key = (round(ph["seg_lat"] * 20) / 20, round(ph["seg_lon"] * 20) / 20)
        if key not in looked_up:
            if len(looked_up) < 6:   # Limit API calls
                looked_up[key] = reverse_geocode_short(key[0], key[1])
            else:
                looked_up[key] = f"{key[0]:.2f}°N"
        place = looked_up[key]
        groups.setdefault(place, []).append(ph)

    parts = []
    for place, phs in groups.items():
        h = sum(1 for p in phs if p.get("severity") == "High")
        m = sum(1 for p in phs if p.get("severity") == "Medium")
        lo = sum(1 for p in phs if p.get("severity") == "Low")
        seg_parts = []
        if h: seg_parts.append(f"**{h} high-severity**")
        if m: seg_parts.append(f"**{m} medium**")
        if lo: seg_parts.append(f"**{lo} low**")
        parts.append(f"{' + '.join(seg_parts)} near **{place}**")

    total_h = sum(1 for p in matched if p.get("severity") == "High")
    total_ph = len(matched)
    risk_txt = "High risk" if total_h >= 2 else ("Moderate risk" if total_ph >= 3 else "Low risk")
    return f"{risk_txt} — This route contains {'; '.join(parts)}."

# ══════════════════════════════════════════════════════════════════════════════
# PAGE LAYOUT
# ══════════════════════════════════════════════════════════════════════════════

st.markdown('<h3 style="margin-bottom:.75rem;">Enter Locations</h3>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1: source      = st.text_input("Starting Point", value="", placeholder="Enter starting location")
with c2: destination = st.text_input("Destination",    value="", placeholder="Enter destination")

if st.button("Calculate & Score Routes", use_container_width=True):
    if not source.strip() or not destination.strip():
        st.warning("Please enter both starting point and destination.")
        st.stop()
        
    # ── Geocode ────────────────────────────────────────────────────────────────
    with st.spinner("Geocoding locations…"):
        try: 
            slat, slon, sname, s_src = geocode(source)
        except Exception as e: 
            st.error(f"Source Error — {e}"); st.stop()
            
        try: 
            dlat, dlon, dname, d_src = geocode(destination)
        except Exception as e: 
            st.error(f"Destination Error — {e}"); st.stop()

    if show_debug:
        with st.expander("🔍 Coordinates"):
            d1, d2 = st.columns(2)
            with d1: st.code(f"Source\nLat:{slat}\nLon:{slon}\n{sname}")
            with d2: st.code(f"Dest\nLat:{dlat}\nLon:{dlon}\n{dname}")

    # ── Fetch routes ───────────────────────────────────────────────────────────
    with st.spinner("Fetching routes from OSRM…"):
        try: routes = get_osrm_routes(slat, slon, dlat, dlon)
        except Exception as e: st.error(f"Routing error — {e}"); st.stop()

    # ── Load active potholes once ──────────────────────────────────────────────
    all_ph  = db_manager.get_active_potholes()
    have_ph = len(all_ph) > 0

    # ── Analyse each route ─────────────────────────────────────────────────────
    with st.spinner("Scoring routes against pothole database…"):
        for rt in routes:
            rt["matched"] = analyse_route(rt["coords"], all_ph, radius_m)
            rt["score"]   = score_potholes(rt["matched"])
            rt["corridors"] = build_corridor_segments(rt["coords"], rt["matched"], radius_m)

        # Compute comfort indices (needs max score across all routes)
        all_totals = [rt["score"]["total"] for rt in routes]
        max_score  = max(all_totals) if any(t > 0 for t in all_totals) else 0
        for rt in routes:
            rt["comfort"] = comfort_index(rt["score"]["total"], max_score)

        safest_idx = min(range(len(routes)), key=lambda i: routes[i]["score"]["total"])

        # ── Route explanations (with reverse geocode) ──────────────────────────
        with st.spinner("Generating route explanations…"):
            for i, rt in enumerate(routes):
                rt["explanation"] = build_explanation(rt["matched"], f"Route {chr(65+i)}")

    st.success(f"{len(routes)} route(s) analysed — "
               f"{'scored against ' + str(len(all_ph)) + ' active potholes' if have_ph else 'no pothole data in DB'}")

    # ── Map ────────────────────────────────────────────────────────────────────
    st.markdown('<h3 style="margin:1.5rem 0 .75rem;">Route Map with Danger Segments</h3>', unsafe_allow_html=True)
    rmap = folium.Map(location=[(slat+dlat)/2, (slon+dlon)/2],
                      zoom_start=7, tiles="CartoDB positron")

    # Draw base routes
    for i, rt in enumerate(routes):
        safe  = (i == safest_idx)
        color = "#10B981" if safe else _RCOLS[i % len(_RCOLS)]
        label = f"Route {chr(65+i)}" + (" ✅ RECOMMENDED" if safe else "")
        sc    = rt["score"]
        tip   = (f"{label} | {rt['distance_km']}km {rt['duration_min']}min"
                 f" | Risk:{sc['total']} 🔴{sc['high']} 🟡{sc['medium']} 🟢{sc['low']}"
                 f" | Comfort:{rt['comfort']}/100")
        folium.PolyLine(rt["coords"], color=color,
                        weight=7 if safe else 4,
                        opacity=0.7 if safe else 0.4,
                        tooltip=tip).add_to(rmap)

        # ── Highway Corridor Mode Overlays ──────────────────────────────────────
        for idx, seg in enumerate(rt["corridors"]):
            if seg["score"] == 0 and not safe: continue  # Only draw excellent segments for the safest route to avoid clutter
            
            # Lookup road name for popup
            mid_lat, mid_lon = rt["coords"][seg["mid_idx"]]
            road_name = get_road_name_cached(mid_lat, mid_lon)
            
            popup_html = f"""
            <div style="font-family:'Inter',sans-serif;min-width:200px;">
              <h4 style="margin:0 0 5px;color:#1E293B;">{road_name}</h4>
              <p style="margin:0 0 10px;font-size:13px;color:#64748B;">Segment {{idx+1}}</p>
              <div style="background:{{seg['color']}}22;border:1px solid {{seg['color']}};padding:5px 10px;border-radius:6px;color:{{seg['color']}};font-weight:600;margin-bottom:10px;text-align:center;">
                Condition: {{seg['condition'].upper()}}
              </div>
              <div style="display:flex;justify-content:space-between;font-size:13px;border-bottom:1px solid #E2E8F0;padding:4px 0;">
                <span>Total Potholes</span><span style="font-weight:600;">{{seg['high']+seg['medium']+seg['low']}}</span>
              </div>
              <div style="display:flex;justify-content:space-between;font-size:13px;border-bottom:1px solid #E2E8F0;padding:4px 0;">
                <span>High</span><span style="font-weight:600;">{{seg['high']}}</span>
              </div>
              <div style="display:flex;justify-content:space-between;font-size:13px;border-bottom:1px solid #E2E8F0;padding:4px 0;">
                <span>Medium</span><span style="font-weight:600;">{{seg['medium']}}</span>
              </div>
              <div style="display:flex;justify-content:space-between;font-size:13px;padding:4px 0;">
                <span>Low</span><span style="font-weight:600;">{{seg['low']}}</span>
              </div>
            </div>
            """
            
            tip = f"{{road_name}} — {{seg['condition']}} (High: {{seg['high']}}, Medium: {{seg['medium']}}, Low: {{seg['low']}})"
            
            folium.PolyLine(
                seg["coords"],
                color=seg["color"],
                weight=8 if seg["score"] > 2 else 5,
                opacity=0.85,
                tooltip=tip,
                popup=folium.Popup(popup_html, max_width=250)
            ).add_to(rmap)

    # Start / End markers
    folium.Marker([slat, slon],
                  popup=folium.Popup(f"<b>Start</b><br>{sname}", max_width=300),
                  icon=folium.Icon(color="green", icon="play", prefix="fa")).add_to(rmap)
    folium.Marker([dlat, dlon],
                  popup=folium.Popup(f"<b>End</b><br>{dname}", max_width=300),
                  icon=folium.Icon(color="red", icon="flag", prefix="fa")).add_to(rmap)

    # Pothole markers — only those matched to ANY route (deduplicated by id)
    if have_ph:
        shown_ids = set()
        for rt in routes:
            for ph in rt["matched"]:
                if ph["id"] in shown_ids: continue
                shown_ids.add(ph["id"])
                sev = ph.get("severity", "Low")
                c   = _SEV_COLOR.get(sev, "#22C55E")
                e   = _SEV_EMOJI.get(sev, "🟢")
                ph_html = (f"<div style='font-family:Inter,sans-serif'>"
                           f"<b>{sev} Pothole #{ph['id']}</b><br>"
                           f"Source: {ph.get('source_type','Historical')}<br>"
                           f"Confidence: {ph['confidence']:.0%}<br>"
                           f"Distance to route: {ph['dist_m']} m</div>")
                folium.CircleMarker(
                    location=[ph["latitude"], ph["longitude"]],
                    radius=8 if sev == "High" else (6 if sev == "Medium" else 5),
                    color=c, fill=True, fill_color=c, fill_opacity=0.9, weight=2,
                    popup=folium.Popup(ph_html, max_width=240),
                    tooltip=f"#{ph['id']} — {sev} ({ph['dist_m']}m)"
                ).add_to(rmap)

    try:
        all_lats = [p[0] for rt in routes for p in rt["coords"]]
        all_lons = [p[1] for rt in routes for p in rt["coords"]]
        rmap.fit_bounds([[min(all_lats), min(all_lons)], [max(all_lats), max(all_lons)]], padding=(40, 40))
        st_folium(rmap, use_container_width=True, height=700, returned_objects=[])
    except Exception as e:
        st.error(f"Failed to render the interactive map: {e}")

    # Legend
    st.markdown("""
    <div style="display:flex;gap:12px;flex-wrap:wrap;margin:8px 0 20px;font-size:13px;">
      <span class="badge badge-green">● Recommended Route</span>
      <span class="badge badge-red">█ Critical / Poor Road</span>
      <span class="badge badge-amber">█ Moderate Road</span>
      <span class="badge badge-green">█ Good / Excellent Road</span>
      <span class="badge badge-red">● High Pothole</span>
      <span class="badge badge-amber">● Medium Pothole</span>
    </div>""", unsafe_allow_html=True)

    # ── Route Comparison Cards ──────────────────────────────────────────────────
    st.markdown('<h3 style="margin:.5rem 0 1rem;">Route Risk Comparison</h3>', unsafe_allow_html=True)
    if not have_ph:
        st.info("No pothole data yet. Run detections to populate the database.")

    cols = st.columns(len(routes))
    for i, (rt, col) in enumerate(zip(routes, cols)):
        safe  = (i == safest_idx)
        sc    = rt["score"]
        hrs   = rt["duration_min"] // 60; mins = rt["duration_min"] % 60
        tstr  = f"{hrs}h {mins}m" if hrs else f"{mins} min"
        total_ph = sc["high"] + sc["medium"] + sc["low"]
        comfort  = rt["comfort"]

        # Calculate overall route condition
        route_cond_str, _ = get_condition(sc["total"] / (rt["distance_km"] / 5.0) if rt["distance_km"] > 0 else 0)

        with col:
            with st.container(border=True):
                if safe:
                    st.success(f"**Route {chr(65+i)}** — Safest Route (Recommended)")
                else:
                    st.info(f"**Route {chr(65+i)}**")
                
                st.write(f"**Distance:** {rt['distance_km']} km")
                st.write(f"**Travel Time:** {tstr}")
                
                if have_ph:
                    st.divider()
                    st.metric("Potholes on Route", total_ph)
                    st.write(f"High: {sc['high']}")
                    st.write(f"Medium: {sc['medium']}")
                    st.write(f"Low: {sc['low']}")
                    
                    st.divider()
                    st.write(f"**Route Condition:** {route_cond_str.upper()}")
                    st.metric("Risk Score", f"{sc['total']} pts")
                    
                    # Ensure comfort is valid for st.progress
                    progress_val = max(0.0, min(1.0, comfort / 100.0))
                    st.progress(progress_val, text=f"Comfort Index: {comfort}/100")
                else:
                    st.info("No pothole data available")

    # ── Route Explanations ─────────────────────────────────────────────────────
    st.markdown('<h3 style="margin:1.5rem 0 .75rem;">Route Explanations</h3>', unsafe_allow_html=True)
    for i, rt in enumerate(routes):
        safe  = (i == safest_idx)
        sc    = rt["score"]
        box_color = "#ECFDF5" if safe else "#FEF2F2"
        border_col = "#A7F3D0" if safe else "#FECACA"
        st.markdown(f"""
        <div style="background:{box_color};border:1px solid {border_col};
                    border-radius:10px;padding:14px 18px;margin-bottom:10px;font-size:13px;line-height:1.6;color:#0F172A;">
          <b style="color:#0F172A;">{f"Route {chr(65+i)}"}</b>
          {'<span class="badge badge-green" style="margin-left:8px;">Recommended</span>' if safe else ''}
          <br>{rt['explanation']}
        </div>""", unsafe_allow_html=True)

    # Removed Exact Scoring Logic, Database Details, and Debug Tables for production view

else:
    # ── Empty state ────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="hero-banner animate-in" style="text-align:center;padding:3rem 2rem;">
      <h3>Enter Locations to Begin Route Scoring</h3>
      <p style="color:#64748B;font-size:13px;max-width:520px;margin:.5rem auto 0;">
        Fetches real driving routes and scores each against your pothole database.<br>
        The safest route is highlighted with segment-level danger overlays.
      </p>
    </div>""", unsafe_allow_html=True)

    s1, s2, s3 = st.columns(3)
    for col, sev, clr, wt in [
        (s1, "High",   "#EF4444", "× 5"),
        (s2, "Medium", "#F59E0B", "× 3"),
        (s3, "Low",    "#10B981", "× 1")
    ]:
        col.markdown(f"""
        <div class="stat-card" style="text-align:center;padding:1.2rem;">
          <div style="font-weight:600;color:{clr};font-size:14px;">{sev}</div>
          <div style="font-size:1.4rem;font-weight:600;color:#0F172A;margin-top:4px;">{wt}</div>
        </div>""", unsafe_allow_html=True)

    # Diagnostics hidden
