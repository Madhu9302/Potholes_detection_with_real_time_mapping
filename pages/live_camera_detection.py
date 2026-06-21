"""
Live Camera Detection — Phase 4
Uses streamlit-webrtc so the webcam runs in a background thread and the
Streamlit UI remains fully interactive (Start / Stop controls work, stats
update, no page freeze).
"""

import streamlit as st
import cv2
import math
import time
import queue
import threading
import numpy as np
from datetime import datetime
from database import db_manager
from utils.sidebar import render_sidebar

# ── streamlit-webrtc ─────────────────────────────────────────────────────────
from streamlit_webrtc import webrtc_streamer, WebRtcMode, VideoProcessorBase
import av

# ── Auth guard ────────────────────────────────────────────────────────────────
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first.")
    st.stop()

# ── CSS ───────────────────────────────────────────────────────────────────────
try:
    with open("assets/style.css", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    pass

render_sidebar()

# ── DB init ───────────────────────────────────────────────────────────────────
db_manager.init_db()

# ── Session-state defaults ────────────────────────────────────────────────────
_defaults = {
    "lcd_detect_count": 0,
    "lcd_log":          [],
    "lcd_gps_lat":      22.7196,
    "lcd_gps_lon":      75.8577,
    "lcd_conf_thresh":  0.40,
    "lcd_frame_skip":   3,
    "lcd_max_log":      10,
    # shared queue written by transformer, read by main thread
    "_lcd_queue":       queue.Queue(maxsize=50),
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Helpers ───────────────────────────────────────────────────────────────────
def _haversine_m(lat1, lon1, lat2, lon2):
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((math.radians(lat2-lat1))/2)**2
         + math.cos(phi1)*math.cos(phi2)*math.sin((math.radians(lon2-lon1))/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def _severity(conf: float) -> str:
    return "High" if conf >= 0.75 else ("Medium" if conf >= 0.50 else "Low")

DIST_M = 20
TIME_S = 60

def upsert_pothole(lat, lon, conf, sev):
    conn = db_manager.get_connection()
    now  = datetime.now()
    rows = conn.execute(
        "SELECT id,latitude,longitude,timestamp FROM pothole_locations "
        "ORDER BY timestamp DESC LIMIT 200"
    ).fetchall()
    matched_id = None
    for row in rows:
        try:
            age = (now - datetime.fromisoformat(str(row["timestamp"]))).total_seconds()
        except Exception:
            continue
        if age > TIME_S:
            continue
        if _haversine_m(lat, lon, row["latitude"], row["longitude"]) <= DIST_M:
            matched_id = row["id"]
            break
    try:
        if matched_id:
            conn.execute(
                "UPDATE pothole_locations SET confidence=?,severity=?,timestamp=? WHERE id=?",
                (conf, sev, now.isoformat(timespec="seconds"), matched_id)
            )
        else:
            conn.execute(
                "INSERT INTO pothole_locations (latitude,longitude,confidence,severity,source_type,timestamp)"
                " VALUES (?,?,?,?,?,?)",
                (lat, lon, conf, sev, "Live Camera", now.isoformat(timespec="seconds"))
            )
        conn.commit()
    finally:
        conn.close()
    return matched_id is not None

def get_today_stats():
    conn  = db_manager.get_connection()
    today = datetime.now().date().isoformat()
    rows  = conn.execute(
        "SELECT severity,timestamp FROM pothole_locations WHERE date(timestamp)=?", (today,)
    ).fetchall()
    conn.close()
    total  = len(rows)
    high   = sum(1 for r in rows if r["severity"]=="High")
    medium = sum(1 for r in rows if r["severity"]=="Medium")
    low    = sum(1 for r in rows if r["severity"]=="Low")
    last_ts = None
    if rows:
        try:
            last_ts = max(datetime.fromisoformat(str(r["timestamp"])) for r in rows)
        except Exception:
            pass
    return total, high, medium, low, last_ts

# ── YOLO model (cached across reruns) ────────────────────────────────────────
@st.cache_resource(show_spinner="⏳ Loading YOLOv11 model…")
def load_yolo():
    from ultralytics import YOLO
    import os
    for c in ["runs/detect/train/weights/best.pt",
              "runs/detect/train2/weights/best.pt",
              "yolo11n.pt"]:
        if os.path.exists(c):
            return YOLO(c)
    return YOLO("yolo11n.pt")

# ── WebRTC Video Transformer ──────────────────────────────────────────────────
class PotholeDetector(VideoProcessorBase):
    """
    Runs in a background thread managed by streamlit-webrtc.
    Reads frames, runs YOLO inference every N frames, annotates,
    and pushes detection events into a thread-safe queue for the
    main Streamlit thread to consume.
    """

    def __init__(self):
        self.model      = load_yolo()
        self.frame_idx  = 0
        # These are set by the main thread via update_params()
        self.conf_thresh = 0.40
        self.frame_skip  = 3
        self.gps_lat     = 22.7196
        self.gps_lon     = 75.8577
        self._lock       = threading.Lock()

    def update_params(self, conf_thresh, frame_skip, lat, lon):
        with self._lock:
            self.conf_thresh = conf_thresh
            self.frame_skip  = frame_skip
            self.gps_lat     = lat
            self.gps_lon     = lon

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")
        self.frame_idx += 1

        with self._lock:
            skip  = self.frame_skip
            thresh = self.conf_thresh
            lat   = self.gps_lat
            lon   = self.gps_lon

        annotated = img.copy()

        if self.frame_idx % skip == 0:
            results = self.model(img, conf=thresh, verbose=False)
            for box in results[0].boxes:
                conf_val = float(box.conf[0])
                x1,y1,x2,y2 = map(int, box.xyxy[0].tolist())
                sev  = _severity(conf_val)
                bgr  = {"High":(0,0,220),"Medium":(0,165,255),"Low":(0,200,80)}[sev]

                # Draw bounding box
                cv2.rectangle(annotated, (x1,y1), (x2,y2), bgr, 2)
                label = f"{sev} {conf_val:.0%}"
                (tw,th),_ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
                cv2.rectangle(annotated, (x1,y1-th-8), (x1+tw+6,y1), bgr, -1)
                cv2.putText(annotated, label, (x1+3,y1-4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255,255,255), 2)

                # Push event to queue (non-blocking, drop if full)
                try:
                    st.session_state["_lcd_queue"].put_nowait({
                        "ts":       datetime.now().strftime("%H:%M:%S"),
                        "conf":     conf_val,
                        "severity": sev,
                        "lat":      lat,
                        "lon":      lon,
                    })
                except queue.Full:
                    pass

        # HUD overlay
        h, w = annotated.shape[:2]
        ts_str = datetime.now().strftime("%H:%M:%S")
        cv2.putText(annotated, ts_str, (w-90, h-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120,120,120), 1)
        cv2.putText(annotated, f"Frame {self.frame_idx}", (8, h-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120,120,120), 1)

        return av.VideoFrame.from_ndarray(annotated, format="bgr24")

# ═════════════════════════════════════════════════════════════════════════════
# PAGE LAYOUT
# ═════════════════════════════════════════════════════════════════════════════

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Detection Settings")
    st.subheader("GPS Coordinates")
    gps_mode = st.radio(
        "Source", ["Manual Entry", "Use Fixed Location"], index=0,
        help="Manual: enter lat/lon below. Fixed: uses Indore city centre."
    )
    if gps_mode == "Manual Entry":
        gps_lat = st.number_input("Latitude",  value=st.session_state.lcd_gps_lat,
                                   format="%.6f", step=0.0001)
        gps_lon = st.number_input("Longitude", value=st.session_state.lcd_gps_lon,
                                   format="%.6f", step=0.0001)
    else:
        gps_lat, gps_lon = 22.7196, 75.8577
        st.info(f"Fixed: {gps_lat:.4f}, {gps_lon:.4f}")

    st.session_state.lcd_gps_lat = gps_lat
    st.session_state.lcd_gps_lon = gps_lon

    conf_thresh = st.slider("Confidence Threshold", 0.20, 0.95,
                             st.session_state.lcd_conf_thresh, 0.05)
    frame_skip  = st.slider("Infer every N frames", 1, 10,
                              st.session_state.lcd_frame_skip,
                              help="Higher = faster feed, fewer false positives.")
    max_log     = st.slider("Log entries to show", 5, 30, st.session_state.lcd_max_log)

    st.session_state.lcd_conf_thresh = conf_thresh
    st.session_state.lcd_frame_skip  = frame_skip
    st.session_state.lcd_max_log     = max_log

    st.markdown("---")
    st.markdown("""
**Duplicate suppression**
- Same location within **20 m**
- Within **60 seconds**
→ Updates existing record instead of inserting new one.
""")

# ── Heading ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="page-header animate-in">
  <h1><span class="gradient-text">Live Camera Detection</span></h1>
  <p class="page-subtitle">Real-time YOLOv11 pothole detection via webcam · Automatic GPS tagging · Live database integration</p>
</div>
""", unsafe_allow_html=True)

# ── Two-column layout: webcam | stats+log ─────────────────────────────────────
col_cam, col_panel = st.columns([3, 2], gap="large")

with col_cam:
    st.subheader("Webcam Feed")
    st.caption("Click **START** inside the widget below, then allow camera access in your browser.")

    # WebRTC streamer — runs in background thread, non-blocking
    ctx = webrtc_streamer(
        key="pothole_live_detector",
        mode=WebRtcMode.SENDRECV,
        video_processor_factory=PotholeDetector,
        media_stream_constraints={"video": True, "audio": False},
        async_processing=True,
        rtc_configuration={
            "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
        },
    )

    # Push latest params into transformer whenever sidebar changes
    if ctx.video_processor is not None:
        ctx.video_processor.update_params(conf_thresh, frame_skip, gps_lat, gps_lon)

    # Status badge
    if ctx.state.playing:
        st.markdown(
            '<span class="live-badge badge-live">● LIVE DETECTION</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="live-badge badge-off">● CAMERA OFFLINE</span>',
            unsafe_allow_html=True,
        )

with col_panel:
    # ── Drain detection queue → update DB + log ────────────────────────────
    if ctx.state.playing:
        drained = 0
        while not st.session_state["_lcd_queue"].empty() and drained < 20:
            try:
                event = st.session_state["_lcd_queue"].get_nowait()
            except queue.Empty:
                break
            updated = upsert_pothole(
                event["lat"], event["lon"],
                event["conf"], event["severity"]
            )
            event["updated"] = updated
            st.session_state.lcd_detect_count += 1
            st.session_state.lcd_log.append(event)
            drained += 1

    # ── Live Statistics ────────────────────────────────────────────────────
    st.subheader("Live Statistics")

    total, high, medium, low, last_ts = get_today_stats()
    last_str = last_ts.strftime("%H:%M:%S") if last_ts else "—"
    session_dets = st.session_state.lcd_detect_count
    gps_status = "Manual Entry" if gps_mode == "Manual Entry" else "Fixed (Indore)"

    st.markdown(f"""
<div class="stat-card s-total">
  <div class="lcd-header">Total Potholes Today</div>
  <div class="lcd-value">{total}</div>
</div>
<div class="stat-card s-high">
  <div class="lcd-header">High Severity</div>
  <div class="lcd-value">{high}</div>
</div>
<div class="stat-card s-medium">
  <div class="lcd-header">Medium Severity</div>
  <div class="lcd-value">{medium}</div>
</div>
<div class="stat-card s-low">
  <div class="lcd-header">Low Severity</div>
  <div class="lcd-value">{low}</div>
</div>
<div class="stat-card s-time">
  <div class="lcd-header">Last Detected At</div>
  <div class="lcd-value" style="font-size:20px">{last_str}</div>
</div>
<div class="stat-card">
  <div class="lcd-header">Detections This Session</div>
  <div class="lcd-value" style="font-size:20px">{session_dets}</div>
</div>
<div class="stat-card s-time">
  <div class="lcd-header">GPS Status</div>
  <div style="font-size:13px;color:#64748B;margin-top:4px;">
    {gps_status}<br>
    <b style="color:#0F172A">{gps_lat:.5f}, {gps_lon:.5f}</b>
  </div>
</div>
<div class="stat-card">
  <div class="lcd-header">Inference Rate</div>
  <div style="font-size:13px;color:#94A3B8;margin-top:4px;">
    Every <b style="color:#F0F4FF">{frame_skip}</b> frames &nbsp;·&nbsp; Conf ≥ <b style="color:#F0F4FF">{conf_thresh:.0%}</b>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Detection Log (full width below) ─────────────────────────────────────────
st.markdown("---")
log_col, clear_col = st.columns([5, 1])
with log_col:
    st.subheader("Detection Log")
with clear_col:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Clear", use_container_width=True):
        st.session_state.lcd_log = []
        st.session_state.lcd_detect_count = 0
        st.rerun()

log = st.session_state.lcd_log
if not log:
    st.info("No detections yet. Start the camera and point it at a pothole.")
else:
    rows_html = ""
    for entry in reversed(log[-max_log:]):
        pill_cls = {
            "High":   "pill-high",
            "Medium": "pill-medium",
            "Low":    "pill-low",
        }.get(entry.get("severity","Low"), "pill-low")
        action = "↺ Updated" if entry.get("updated") else "＋ Inserted"
        rows_html += f"""
<div style="border-bottom:1px solid #1E293B;padding:9px 0;font-size:13px;color:#CBD5E1">
  <span class="det-pill {pill_cls}">{entry.get('severity','—')}</span>
  <b>{action}</b> &nbsp;·&nbsp; {entry.get('ts','—')}<br>
  <span style="color:#64748B">
    Conf: {entry.get('conf',0):.0%} &nbsp;|&nbsp;
    GPS: {entry.get('lat',0):.5f}, {entry.get('lon',0):.5f}
  </span>
</div>"""
    st.markdown(rows_html, unsafe_allow_html=True)

# ── Auto-refresh stats every 5 s while camera is running ─────────────────────
if ctx.state.playing:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=5000, limit=None, key="lcd_autorefresh")

# ── Usage info (shown when idle) ──────────────────────────────────────────────
if not ctx.state.playing:
    st.markdown("---")
    with st.expander("How to use Live Camera Detection", expanded=True):
        st.markdown("""
**Step-by-step:**
1. Set your **GPS coordinates** in the sidebar (or use the fixed Indore location for testing).
2. Adjust **Confidence Threshold** and **Inference rate** to balance speed vs. accuracy.
3. Click **▶ START** inside the webcam widget above and allow browser camera access.
4. Point the camera at a road — detected potholes appear with coloured bounding boxes.
5. Every detection is automatically saved to the database and visible on the **Live Pothole Map**.
6. Click **⏹ STOP** in the widget to end the session.

**Severity colours:**
| Box colour | Severity | Confidence |
|---|---|---|
| Red | High | ≥ 75 % |
| Orange | Medium | 50 – 74 % |
| Green | Low | < 50 % |

**Duplicate suppression:** if the same pothole is detected within **20 m** and **60 s**, the existing database record is updated instead of creating a duplicate.
""")
