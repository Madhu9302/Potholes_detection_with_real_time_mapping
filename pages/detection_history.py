import streamlit as st
import pandas as pd
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

st.markdown("""
<div class="page-header animate-in">
  <h1><span class="gradient-text">Detection History</span></h1>
  <p class="page-subtitle">Filter, search and export all historical pavement inspection records from the local database.</p>
</div>""", unsafe_allow_html=True)

detections = db_manager.get_user_detections(user["id"])

if not detections:
    st.markdown("""
    <div class="hero-banner animate-in" style="text-align:center;padding:3rem 2rem;">
      <h3>No Detection Logs Yet</h3>
      <p style="color:#64748B;font-size:13.5px;">Upload images or videos in the detection pages to populate your history.</p>
    </div>""", unsafe_allow_html=True)
else:
    df = pd.DataFrame(detections)
    df["detected_at"] = pd.to_datetime(df["detected_at"])

    # KPI cards
    st.markdown(f"""
    <div class="kpi-grid animate-in delay-1" style="grid-template-columns:repeat(4,1fr);margin-bottom:1.5rem;">
      <div class="kpi-card">
        <div class="kpi-title">Total Scans</div><div class="kpi-value">{len(df)}</div></div>
      <div class="kpi-card">
        <div class="kpi-title">Potholes Logged</div><div class="kpi-value">{int(df['potholes_count'].sum())}</div></div>
      <div class="kpi-card">
        <div class="kpi-title">Image Scans</div><div class="kpi-value">{int((df['file_type']=='image').sum())}</div></div>
      <div class="kpi-card">
        <div class="kpi-title">Video Scans</div><div class="kpi-value">{int((df['file_type']=='video').sum())}</div></div>
    </div>
    """, unsafe_allow_html=True)

    # ── Filters ───────────────────────────────────────────────────────────────
    st.markdown('<h3 style="margin-bottom:.75rem;">Filter Records</h3>', unsafe_allow_html=True)
    fc1, fc2, fc3, fc4 = st.columns(4)

    with fc1:
        search = st.text_input("Search Filename", placeholder="e.g. nh8")
    with fc2:
        fmt_filter = st.selectbox("Format", ["All","Image","Video"])
    with fc3:
        min_date = df["detected_at"].min().date()
        max_date = df["detected_at"].max().date()
        date_range = st.date_input("Date Range", value=(min_date, max_date),
                                    min_value=min_date, max_value=max_date)
    with fc4:
        mx = int(df["potholes_count"].max())
        ph_range = st.slider("Potholes Count", 0, mx if mx > 0 else 10, (0, mx if mx > 0 else 10))

    fdf = df.copy()
    if search:
        fdf = fdf[fdf["filename"].str.contains(search, case=False, na=False)]
    if fmt_filter != "All":
        fdf = fdf[fdf["file_type"] == fmt_filter.lower()]
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        fdf = fdf[(fdf["detected_at"].dt.date >= date_range[0]) &
                  (fdf["detected_at"].dt.date <= date_range[1])]
    fdf = fdf[(fdf["potholes_count"] >= ph_range[0]) & (fdf["potholes_count"] <= ph_range[1])]

    st.markdown(f'<p style="color:#64748B;font-size:13px;margin-bottom:.75rem;">Showing <b style="color:#0F172A">{len(fdf)}</b> records</p>', unsafe_allow_html=True)

    display = fdf.copy()
    display["detected_at"] = display["detected_at"].dt.strftime("%Y-%m-%d %H:%M:%S")
    display = display.rename(columns={"filename":"File","file_type":"Type","potholes_count":"Potholes","detected_at":"Timestamp"})
    st.dataframe(display[["File","Type","Potholes","Timestamp"]], use_container_width=True, hide_index=True)

    # ── Export ─────────────────────────────────────────────────────────────────
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
    st.markdown('<h3 style="margin-bottom:.75rem;">Export Records</h3>', unsafe_allow_html=True)
    e1, e2, e3 = st.columns([1,1,2])
    with e1:
        st.download_button("Export CSV", fdf.to_csv(index=False).encode("utf-8"),
                           "pothole_history.csv", "text/csv", use_container_width=True)
    with e2:
        st.download_button("Export JSON", fdf.to_json(orient="records", date_format="iso").encode("utf-8"),
                           "pothole_history.json", "application/json", use_container_width=True)
    with e3:
        if st.button("Clear Filtered Logs", type="secondary", use_container_width=True):
            st.warning("To clear logs, modify the SQLite database directly.")
