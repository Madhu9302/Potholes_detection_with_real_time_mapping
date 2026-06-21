import streamlit as st

st.set_page_config(
    page_title="Smart Pothole Detection & Route Planning",
    page_icon=":material/map:",
    layout="wide",
    initial_sidebar_state="expanded"
)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None

auth_page     = st.Page("pages/auth.py",                  title="Authentication")
home_page     = st.Page("pages/home.py",                  title="Home Dashboard", default=True)
image_page    = st.Page("pages/image_detection.py",       title="Image Detection")
video_page    = st.Page("pages/video_detection.py",       title="Video Detection")
live_cam_page = st.Page("pages/live_camera_detection.py", title="Live Camera")
history_page  = st.Page("pages/detection_history.py",     title="Detection History")
map_page      = st.Page("pages/live_pothole_map.py",      title="Live Pothole Map")
route_page    = st.Page("pages/smart_route_planner.py",   title="Smart Route Planner")
mgmt_page     = st.Page("pages/pothole_management.py",    title="Pothole Management")
health_page   = st.Page("pages/system_health.py",         title="System Health Check")

if st.session_state.logged_in:
    pg = st.navigation({
        "Overview":            [home_page],
        "Detection Pipelines": [image_page, video_page, live_cam_page],
        "GIS & Telemetry":     [map_page, route_page, history_page],
        "Management":          [mgmt_page],
        "System":              [health_page]
    })
    pg.run()
else:
    pg = st.navigation([auth_page])
    pg.run()
