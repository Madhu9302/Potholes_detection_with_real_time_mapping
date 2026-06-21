import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime
from database import db_manager
from utils.sidebar import render_sidebar

if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first."); st.stop()

user = st.session_state.user
try:
    with open("assets/style.css", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    pass

render_sidebar()

db_manager.init_db()

# Demo Mode functionality removed

# ── Load data ─────────────────────────────────────────────────────────────────
stats      = db_manager.get_detection_stats(user["id"])
map_stats  = db_manager.get_pothole_map_stats()
detections = db_manager.get_user_detections(user["id"])

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="hero-banner animate-in">
  <div style="display:flex;align-items:center;gap:14px;margin-bottom:.4rem;">
    <div>
      <h1 style="margin:0!important;font-size:1.75rem!important;">
        Welcome back, <span class="gradient-text">{user["username"]}</span>
      </h1>
      <p style="color:#64748B;font-size:14px;margin:4px 0 0;">
        Smart Pothole Detection &amp; Route Planning — Enterprise Monitoring Dashboard
      </p>
    </div>
    <div style="margin-left:auto;display:flex;gap:8px;flex-wrap:wrap;">
      <span class="badge badge-green">System Online</span>
      <span class="badge badge-indigo">v3.0</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── KPI Grid ──────────────────────────────────────────────────────────────────
last_ts_str = map_stats["last_ts"] or "—"
st.markdown(f"""
<div class="kpi-grid animate-in delay-1">
  <div class="kpi-card">
    <div class="kpi-title">Total Potholes</div>
    <div class="kpi-value">{map_stats['total']}</div>
    <div class="kpi-desc">All geo-tagged records</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-title">Active</div>
    <div class="kpi-value" style="color:#10B981;">{map_stats['active']}</div>
    <div class="kpi-desc">On map &amp; route planner</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-title">Resolved</div>
    <div class="kpi-value" style="color:#64748B;">{map_stats['resolved']}</div>
    <div class="kpi-desc">Hidden from map</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-title">Resolution Rate</div>
    <div class="kpi-value" style="color:#0284C7;">{map_stats['resolution_rate']}%</div>
    <div class="kpi-desc">Resolved ÷ Total</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-title">High Severity</div>
    <div class="kpi-value" style="color:#EF4444;">{map_stats['high']}</div>
    <div class="kpi-desc">Critical hazards</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-title">Historical</div>
    <div class="kpi-value">{map_stats['historical']}</div>
    <div class="kpi-desc">Permanent baseline</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── System Health & Last Detection ────────────────────────────────────────────
col_health, col_last = st.columns([1, 1], gap="large")

with col_health:
    yolo_ok = any(os.path.exists(p) for p in [
        "runs/detect/train/weights/best.pt",
        "runs/detect/train2/weights/best.pt",
        "runs/detect/train4/weights/best.pt",
        "yolo11n.pt"
    ])
    yolo_dot  = "dot-green" if yolo_ok  else "dot-amber"
    yolo_txt  = "Loaded" if yolo_ok else "Default (yolo11n)"
    db_path   = "database/pothole_system.db"
    db_ok     = os.path.exists(db_path)
    db_dot    = "dot-green" if db_ok else "dot-red"
    db_txt    = "Connected" if db_ok else "Not Found"

    st.markdown(f"""
    <div class="stat-card s-total" style="padding:1.2rem 1.4rem;">
      <div class="lcd-header" style="margin-bottom:12px;">System Health</div>
      <div class="health-row">
        <span><span class="health-dot {yolo_dot}"></span>YOLO Model</span>
        <span class="badge {'badge-green' if yolo_ok else 'badge-amber'}">{yolo_txt}</span>
      </div>
      <div class="health-row">
        <span><span class="health-dot {db_dot}"></span>SQLite Database</span>
        <span class="badge {'badge-green' if db_ok else 'badge-red'}">{db_txt}</span>
      </div>
      <div class="health-row">
        <span><span class="health-dot dot-green"></span>GPS Integration</span>
        <span class="badge badge-green">Browser API</span>
      </div>
      <div class="health-row">
        <span><span class="health-dot dot-green"></span>WebRTC Camera</span>
        <span class="badge badge-green">Available</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

with col_last:
    st.markdown(f"""
    <div class="stat-card s-time" style="padding:1.2rem 1.4rem;">
      <div class="lcd-header" style="margin-bottom:12px;">Scan Summary</div>
      <div class="health-row">
        <span class="label">Image Scans</span>
        <span class="value">{stats['image_detections']}</span>
      </div>
      <div class="health-row">
        <span class="label">Video Scans</span>
        <span class="value">{stats['video_detections']}</span>
      </div>
      <div class="health-row">
        <span class="label">Potholes Flagged</span>
        <span class="value">{stats['total_potholes']}</span>
      </div>
      <div class="health-row">
        <span class="label">Avg / Scan</span>
        <span class="value">{stats['avg_potholes']}</span>
      </div>
      <div class="health-row">
        <span class="label">Last Detection</span>
        <span class="value" style="font-size:12px;">{str(last_ts_str)[:19]}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── Charts ────────────────────────────────────────────────────────────────────
st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
st.markdown('<h3 style="margin-bottom:1rem;">Analytical Trends</h3>', unsafe_allow_html=True)

_layout = dict(
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=10,r=10,t=40,b=20),
    font=dict(family="Inter,sans-serif", color="#64748B", size=12),
    title_font=dict(color="#0F172A", size=14)
)
c1, c2 = st.columns(2)
if detections:
    df = pd.DataFrame(detections)
    df["detected_at"] = pd.to_datetime(df["detected_at"])
    df["Date"] = df["detected_at"].dt.date
    tl = df.groupby("Date")["potholes_count"].sum().reset_index()
    fig1 = px.area(tl, x="Date", y="potholes_count", title="Potholes Detected Over Time",
                   labels={"potholes_count":"Count","Date":"Date"}, template="plotly_white")
    fig1.update_traces(line_color="#0EA5E9", fillcolor="rgba(14,165,233,0.15)", line_width=2.5)
    fig1.update_layout(**_layout)
    fig1.update_xaxes(gridcolor="rgba(0,0,0,0.05)", zeroline=False)
    fig1.update_yaxes(gridcolor="rgba(0,0,0,0.05)", zeroline=False)

    td = df.groupby("file_type")["filename"].count().reset_index()
    td.columns = ["Type","Count"]
    fig2 = px.pie(td, values="Count", names="Type", title="Media Type Breakdown",
                  color="Type", color_discrete_map={"image":"#38BDF8","video":"#0EA5E9"},
                  template="plotly_white")
    fig2.update_traces(textfont_color="#FFFFFF")
    fig2.update_layout(**_layout)
    with c1: st.plotly_chart(fig1, use_container_width=True)
    with c2: st.plotly_chart(fig2, use_container_width=True)
else:
    with c1: st.info("No scan data yet. Run a detection to populate charts.")
    with c2: st.info("No media type data yet.")

# ── Recent Activity ───────────────────────────────────────────────────────────
st.markdown('<h3 style="margin:1.5rem 0 .75rem;">Recent Detection Activity</h3>', unsafe_allow_html=True)
if detections:
    df2 = pd.DataFrame(detections).head(8)
    df2["detected_at"] = pd.to_datetime(df2["detected_at"]).dt.strftime("%Y-%m-%d %H:%M")
    df2 = df2.rename(columns={"filename":"File","file_type":"Type","potholes_count":"Potholes","detected_at":"Timestamp"})
    st.dataframe(df2[["File","Type","Potholes","Timestamp"]], use_container_width=True, hide_index=True)
else:
    st.info("No detection history yet.")

# End of home.py
