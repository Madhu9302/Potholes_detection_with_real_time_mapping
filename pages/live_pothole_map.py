import streamlit as st
import folium
from folium.plugins import MarkerCluster, HeatMap
from streamlit_folium import st_folium
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
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

_refresh = st_autorefresh(interval=10000, limit=None, key="map_autorefresh")
db_manager.init_db()

# Custom CSS for glassmorphism, floating legend, and animations
st.markdown("""
<style>
/* Glassmorphism KPI Cards */
.gis-kpi-container {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1.5rem;
    margin-bottom: 1.5rem;
}
.gis-kpi-card {
    background: rgba(15, 30, 56, 0.45);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    padding: 1.5rem;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
    position: relative;
    overflow: hidden;
}
.gis-kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; width: 100%; height: 3px;
}
.gis-kpi-card.c-active::before { background: linear-gradient(90deg, #3B82F6, #60A5FA); }
.gis-kpi-card.c-high::before { background: linear-gradient(90deg, #EF4444, #F87171); }
.gis-kpi-card.c-resolved::before { background: linear-gradient(90deg, #10B981, #34D399); }
.gis-kpi-card.c-routes::before { background: linear-gradient(90deg, #8B5CF6, #A78BFA); }

.gis-kpi-value {
    font-size: 2.2rem;
    font-weight: 800;
    color: #F8FAFC;
    line-height: 1.1;
    margin-bottom: 0.2rem;
}
.gis-kpi-label {
    font-size: 0.85rem;
    font-weight: 600;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* Floating Legend */
.floating-legend {
    background: rgba(15, 30, 56, 0.75);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px;
    padding: 15px;
    color: #F8FAFC;
    font-size: 13px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.5);
}
.legend-item {
    display: flex;
    align-items: center;
    margin-bottom: 8px;
}
.legend-item:last-child { margin-bottom: 0; }
.legend-color {
    width: 12px; height: 12px; border-radius: 50%;
    margin-right: 10px;
}

/* Animated Markers */
.pulse-marker {
    width: 16px; height: 16px;
    border-radius: 50%;
    position: relative;
}
.pulse-marker.high { background: rgba(239, 68, 68, 1); box-shadow: 0 0 0 rgba(239, 68, 68, 0.4); animation: pulse-high 2s infinite; }
.pulse-marker.medium { background: rgba(245, 158, 11, 1); box-shadow: 0 0 0 rgba(245, 158, 11, 0.4); animation: pulse-medium 2s infinite; }
.pulse-marker.low { background: rgba(16, 185, 129, 1); box-shadow: 0 0 0 rgba(16, 185, 129, 0.4); animation: pulse-low 2s infinite; }

@keyframes pulse-high { 0% { box-shadow: 0 0 0 0 rgba(239,68,68,0.7); } 70% { box-shadow: 0 0 0 15px rgba(239,68,68,0); } 100% { box-shadow: 0 0 0 0 rgba(239,68,68,0); } }
@keyframes pulse-medium { 0% { box-shadow: 0 0 0 0 rgba(245,158,11,0.7); } 70% { box-shadow: 0 0 0 12px rgba(245,158,11,0); } 100% { box-shadow: 0 0 0 0 rgba(245,158,11,0); } }
@keyframes pulse-low { 0% { box-shadow: 0 0 0 0 rgba(16,185,129,0.7); } 70% { box-shadow: 0 0 0 10px rgba(16,185,129,0); } 100% { box-shadow: 0 0 0 0 rgba(16,185,129,0); } }

/* Stretch layout */
[data-testid="block-container"] {
    max-width: 100% !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="margin-bottom: 1.5rem;">
  <h1 style="margin-bottom: 0;"><span class="gradient-text">Command Center: Pothole Map</span></h1>
  <p style="color:#64748B; margin-top: 5px;">Road Infrastructure Monitoring & Live Telemetry</p>
</div>
""", unsafe_allow_html=True)

# ── Stats ──────────────────────────────────────────────────────────────────────
ms = db_manager.get_pothole_map_stats()
# Mock routes protected for dashboard realism
routes_protected = 14 if ms["active"] > 0 else 0

st.markdown(f"""
<div class="gis-kpi-container">
    <div class="gis-kpi-card c-active">
        <div class="gis-kpi-label">Active Hazards</div>
        <div class="gis-kpi-value">{ms['active']}</div>
    </div>
    <div class="gis-kpi-card c-high">
        <div class="gis-kpi-label">High Severity</div>
        <div class="gis-kpi-value" style="color:#FCA5A5;">{ms['high']}</div>
    </div>
    <div class="gis-kpi-card c-resolved">
        <div class="gis-kpi-label">Resolved</div>
        <div class="gis-kpi-value" style="color:#6EE7B7;">{ms['resolved']}</div>
    </div>
    <div class="gis-kpi-card c-routes">
        <div class="gis-kpi-label">Routes Protected</div>
        <div class="gis-kpi-value" style="color:#A78BFA;">{routes_protected}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Filters ────────────────────────────────────────────────────────────────────
with st.expander("Dashboard Controls", expanded=False):
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        source_filter = st.multiselect("Source", ["Historical","Image Detection","Video Detection","Live Camera"], default=["Historical","Image Detection","Video Detection","Live Camera"])
    with fc2:
        sev_filter = st.multiselect("Severity", ["High","Medium","Low"], default=["High","Medium","Low"])
    with fc3:
        min_conf = st.slider("Confidence Threshold", 0.0, 1.0, 0.0, step=0.05)

# ── Load & filter data ────────────────────────────────────────────────────────
all_ph = db_manager.get_active_potholes()

if all_ph:
    df = pd.DataFrame(all_ph)
    df = df[
        df["source_type"].isin(source_filter) &
        df["severity"].isin(sev_filter) &
        (df["confidence"] >= min_conf)
    ]
else:
    df = pd.DataFrame()

center_lat = float(df["latitude"].mean())  if not df.empty else 22.7196
center_lng = float(df["longitude"].mean()) if not df.empty else 75.8577
zoom_val   = 12 if not df.empty else 13

# ── Build map ──────────────────────────────────────────────────────────────────
m = folium.Map(location=[center_lat, center_lng], zoom_start=zoom_val, max_zoom=19,
               tiles="CartoDB positron", control_scale=True)

# Feature Groups for Layer Control
fg_clusters = folium.FeatureGroup(name="Clusters", show=True)
fg_heatmap = folium.FeatureGroup(name="Heatmap", show=False)
fg_markers = folium.FeatureGroup(name="Individual Markers", show=False)

cluster = MarkerCluster().add_to(fg_clusters)
heat_data = []

_SEV_COLOR = {"High": "#EF4444", "Medium": "#F59E0B", "Low": "#10B981"}

for _, row in df.iterrows() if not df.empty else pd.DataFrame().iterrows():
    sev    = row["severity"]
    src    = row.get("source_type","Historical")
    color  = _SEV_COLOR.get(sev, "#10B981")
    
    # Heatmap data (weight by severity)
    weight = 1.0 if sev == "High" else (0.6 if sev == "Medium" else 0.3)
    heat_data.append([float(row["latitude"]), float(row["longitude"]), weight])
    
    popup_html = f"""
    <div style="font-family:'Inter',sans-serif;color:#1E293B;line-height:1.6;min-width:220px;padding:5px;">
      <h4 style="margin:0 0 8px;color:#0F1E38;border-bottom:2px solid {color};padding-bottom:4px;">Hazard #{int(row['id'])}</h4>
      <table style="width:100%;font-size:12px;">
        <tr><td style="color:#64748B;padding:2px 0;">Severity</td><td style="text-align:right;font-weight:700;color:{color};">{sev}</td></tr>
        <tr><td style="color:#64748B;padding:2px 0;">Confidence</td><td style="text-align:right;font-weight:600;">{float(row['confidence']):.1%}</td></tr>
        <tr><td style="color:#64748B;padding:2px 0;">Source</td><td style="text-align:right;font-weight:600;">{src}</td></tr>
        <tr><td style="color:#64748B;padding:2px 0;">Detected</td><td style="text-align:right;">{str(row['timestamp'])[:16]}</td></tr>
      </table>
    </div>"""

    # Animated Icon for individual markers
    icon_class = "high" if sev == "High" else ("medium" if sev == "Medium" else "low")
    anim_icon = folium.DivIcon(
        html=f'<div class="pulse-marker {icon_class}"></div>',
        icon_size=(16, 16),
        icon_anchor=(8, 8)
    )

    # Standard circle for clusters to keep it clean
    folium.CircleMarker(
        location=[float(row["latitude"]), float(row["longitude"])],
        radius=8 if sev=="High" else (6 if sev=="Medium" else 4),
        popup=folium.Popup(popup_html, max_width=280),
        tooltip=f"#{int(row['id'])} - {sev}",
        color=color, fill=True, fill_color=color, fill_opacity=0.7, weight=1
    ).add_to(cluster)

    # Animated marker for individual layer
    folium.Marker(
        location=[float(row["latitude"]), float(row["longitude"])],
        icon=anim_icon,
        popup=folium.Popup(popup_html, max_width=280),
        tooltip=f"#{int(row['id'])} - {sev}"
    ).add_to(fg_markers)

if heat_data:
    HeatMap(heat_data, radius=15, blur=20, min_opacity=0.4, gradient={0.4: '#10B981', 0.65: '#F59E0B', 1.0: '#EF4444'}).add_to(fg_heatmap)

fg_clusters.add_to(m)
fg_heatmap.add_to(m)
fg_markers.add_to(m)

# Layer Control
folium.LayerControl(collapsed=False).add_to(m)

# Floating Legend
legend_html = """
<div style="position: absolute; bottom: 30px; left: 30px; z-index: 1000;" class="floating-legend">
    <div style="font-weight: 700; margin-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 5px;">Hazard Levels</div>
    <div class="legend-item"><div class="legend-color" style="background:#EF4444;box-shadow:0 0 8px #EF4444;"></div> High Severity</div>
    <div class="legend-item"><div class="legend-color" style="background:#F59E0B;box-shadow:0 0 8px #F59E0B;"></div> Medium Severity</div>
    <div class="legend-item"><div class="legend-color" style="background:#10B981;box-shadow:0 0 8px #10B981;"></div> Low Severity</div>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

st_folium(m, width="100%", height=700, returned_objects=[])

if df.empty:
    st.info("No active hazards match the current filters.")
