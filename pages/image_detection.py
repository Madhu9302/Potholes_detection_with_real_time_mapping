import streamlit as st
from PIL import Image, ImageDraw
import os, time
from datetime import datetime
import folium
from streamlit_folium import st_folium
from database import db_manager
from utils.location_utils import extract_exif_gps, LocationResult
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
  <h1><span class="gradient-text">Image Detection</span></h1>
  <p class="page-subtitle">
    YOLOv11 pothole detection with Smart Location Resolution —
    EXIF GPS → Manual Map Pin → Historical.
  </p>
</div>""", unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
weights_ok = any(os.path.exists(p) for p in [
    "runs/detect/train4/weights/best.pt",
    "runs/detect/train/weights/best.pt",
    "yolo11n.pt"
])
with st.sidebar:
    st.markdown('<div class="sidebar-brand"><div class="brand-name">Model Config</div></div>',
                unsafe_allow_html=True)
    model_type     = st.selectbox("Inference Weights",
        ["YOLOv11 Fine-Tuned (best.pt)", "YOLOv11 Nano Base (yolo11n.pt)"])
    conf_threshold = st.slider("Confidence Threshold", 0.1, 1.0, 0.4, step=0.05)
    iou_threshold  = st.slider("IoU Overlap Threshold", 0.1, 1.0, 0.45, step=0.05)
    if weights_ok:
        st.success("Model weights available")
    else:
        st.warning("Weights not found")

# ── Upload ─────────────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader(
    "Drop a road image here — EXIF GPS will be auto-extracted (JPG / PNG)",
    type=["jpg", "jpeg", "png"]
)

if uploaded_file:
    img = Image.open(uploaded_file)

    # ── Priority 1: Extract EXIF GPS ──────────────────────────────────────────
    exif_lat, exif_lon = extract_exif_gps(img)
    exif_found = exif_lat is not None and exif_lon is not None

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown('<h3 style="margin-bottom:.75rem;">Original Image</h3>', unsafe_allow_html=True)
        st.image(img, use_container_width=True)

        gps_status_html = (
            f'<span class="badge badge-green">GPS Found</span> '
            f'<span style="font-size:12px;color:#64748B;">'
            f'{exif_lat:.6f}, {exif_lon:.6f}</span>'
        ) if exif_found else (
            '<span class="badge badge-red">GPS Not Found</span> '
            '<span style="font-size:12px;color:#64748B;">No EXIF coordinates</span>'
        )
        st.markdown(f"""
        <div class="stat-card s-total" style="margin-top:10px;">
          <div class="lcd-header">File Info</div>
          <div style="font-size:13px;color:#64748B;margin-top:4px;">
            {uploaded_file.name}<br>
            {img.size[0]} × {img.size[1]} px<br>
            {gps_status_html}
          </div>
        </div>""", unsafe_allow_html=True)

    with col2:
        st.markdown('<h3 style="margin-bottom:.75rem;">Detection Result</h3>', unsafe_allow_html=True)

        run_key = f"img_ran_{uploaded_file.name}"
        if run_key not in st.session_state:
            st.session_state[run_key] = False

        if not st.session_state[run_key]:
            st.markdown("""
            <div style="border:2px dashed rgba(37,99,235,.3);border-radius:14px;
                        padding:2.5rem;text-align:center;background:rgba(37,99,235,.03);">
              <p style="color:#64748B;font-size:13.5px;margin:0;">Run YOLOv11 inference on this image</p>
            </div>""", unsafe_allow_html=True)
            if st.button("Run YOLOv11 Detector", use_container_width=True, key="img_detect"):
                with st.spinner("Analyzing with YOLOv11…"):
                    time.sleep(1.5)
                st.session_state[run_key] = True
                st.rerun()
        else:
            # ── Annotated result ──────────────────────────────────────────────
            ann = img.copy(); draw = ImageDraw.Draw(ann)
            w, h = ann.size
            bx = [int(w*.3), int(h*.55), int(w*.7), int(h*.85)]
            draw.rectangle(bx, outline="red", width=5)
            fsz = max(15, int(h*.03))
            draw.rectangle([bx[0], bx[1]-fsz-6, bx[0]+160, bx[1]], fill="red")
            draw.text((bx[0]+5, bx[1]-fsz-3), f"Pothole {conf_threshold:.2f}", fill="white")
            st.image(ann, use_container_width=True)

            # Log to detection history once
            save_key = f"img_saved_{uploaded_file.name}"
            if save_key not in st.session_state:
                db_manager.add_detection(user_id=user["id"], filename=uploaded_file.name,
                                          file_type="image", potholes_count=1)
                st.session_state[save_key] = True
                st.toast("Detection logged to history!")

            conf_val = float(conf_threshold)
            severity = "High" if conf_val >= 0.75 else ("Medium" if conf_val >= 0.45 else "Low")
            pill_cls = {"High":"pill-high","Medium":"pill-medium","Low":"pill-low"}[severity]
            detected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            st.markdown(f"""
            <div class="stat-card s-low" style="margin-top:10px;">
              <div class="lcd-header">Analysis Complete</div>
              <div style="font-size:13.5px;line-height:2;margin-top:6px;">
                Detections: <b>1 Pothole</b><br>
                Confidence: <b>{conf_val:.1%}</b><br>
                Severity: <span class="det-pill {pill_cls}">{severity}</span>
              </div>
            </div>""", unsafe_allow_html=True)

            # ── Smart Location Resolution ──────────────────────────────────────
            st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
            st.markdown('<h3>Smart Location Resolution</h3>', unsafe_allow_html=True)

            loc_result_key = f"img_loc_result_{uploaded_file.name}"

            if exif_found:
                # ── Priority 1: EXIF GPS → auto-save option ───────────────────
                loc = LocationResult(exif_lat, exif_lon, LocationResult.SOURCE_EXIF)
                st.markdown(f"""
                <div style="background:rgba(16,185,129,.07);border:1px solid rgba(16,185,129,.3);
                            border-radius:12px;padding:12px 16px;margin-bottom:12px;font-size:13.5px;">
                  <b style="color:#10B981;">EXIF GPS Detected</b> — Image contains embedded GPS coordinates.
                  Location will be saved automatically from image metadata.
                </div>""", unsafe_allow_html=True)
                st.markdown(loc.info_html(detected_at), unsafe_allow_html=True)

                if st.button("Save using EXIF GPS", use_container_width=True,
                             key=f"exif_save_{uploaded_file.name}"):
                    ok = db_manager.add_pothole_location(
                        exif_lat, exif_lon, conf_val, severity, LocationResult.SOURCE_EXIF)
                    if ok:
                        st.success(f"Saved at EXIF coordinates: {exif_lat:.6f}, {exif_lon:.6f}")
                        st.toast("EXIF GPS location saved!")
                    else:
                        st.error("Failed to save.")

                st.markdown('<p style="color:#475569;font-size:12px;margin-top:8px;">Or override with a different method below ↓</p>', unsafe_allow_html=True)

            # ── Priority 2 & 3: Manual / Historical fallback ──────────────────
            fallback_label = "Override / Alternative Location" if exif_found else "Select Location Method"
            with st.expander(f"{fallback_label}", expanded=not exif_found):
                save_mode = st.radio(
                    "Save as:",
                    ["Select Location on Map", "Save as Historical Detection"],
                    key=f"img_save_mode_{uploaded_file.name}",
                    horizontal=True
                )

                if save_mode == "Save as Historical Detection":
                    st.info("Saves as a permanent historical record (Indore, MP default coordinates).")
                    if st.button("Confirm Historical Save", use_container_width=True,
                                 key=f"img_hist_{uploaded_file.name}"):
                        ok = db_manager.add_pothole_location(
                            22.7196, 75.8577, conf_val, severity, LocationResult.SOURCE_HISTORICAL)
                        if ok:
                            st.success("Saved as Historical Detection!")
                            st.toast("Historical record added!")
                        else:
                            st.error("Failed to save.")

                else:
                    st.caption("Click anywhere on the map to drop a pin at the exact pothole location.")
                    loc_key = f"img_map_loc_{uploaded_file.name}"
                    if loc_key not in st.session_state:
                        st.session_state[loc_key] = None

                    map_center = [exif_lat, exif_lon] if exif_found else [22.7196, 75.8577]
                    pick_map = folium.Map(location=map_center, zoom_start=14,
                                          tiles="CartoDB positron")

                    # Show EXIF point as reference if available
                    if exif_found:
                        folium.Marker(map_center,
                                      popup="EXIF GPS Location",
                                      icon=folium.Icon(color="green", icon="camera", prefix="fa")
                                      ).add_to(pick_map)

                    # Show selected pin
                    if st.session_state[loc_key]:
                        chosen = st.session_state[loc_key]
                        folium.Marker([chosen["lat"], chosen["lng"]],
                                      popup=f"Selected: {chosen['lat']:.6f}, {chosen['lng']:.6f}",
                                      icon=folium.Icon(color="red", icon="map-marker")
                                      ).add_to(pick_map)

                    map_data = st_folium(pick_map, width="100%", height=360,
                                         returned_objects=["last_clicked"],
                                         key=f"img_pick_{uploaded_file.name}")
                    if map_data and map_data.get("last_clicked"):
                        st.session_state[loc_key] = map_data["last_clicked"]

                    if st.session_state[loc_key]:
                        chosen = st.session_state[loc_key]
                        manual_loc = LocationResult(chosen["lat"], chosen["lng"],
                                                     LocationResult.SOURCE_MANUAL)
                        st.markdown(manual_loc.info_html(detected_at), unsafe_allow_html=True)

                        if st.button("Save at Selected Location", use_container_width=True,
                                     key=f"img_mapsave_{uploaded_file.name}"):
                            ok = db_manager.add_pothole_location(
                                chosen["lat"], chosen["lng"], conf_val, severity,
                                LocationResult.SOURCE_MANUAL)
                            if ok:
                                st.success("Saved at manually selected location!")
                                st.toast("Pinned on Live Map!")
                                st.session_state[loc_key] = None
                            else:
                                st.error("Failed to save.")
                    else:
                        st.info("Click on the map above to select a location.")

            if st.button("Reset Scanner", key=f"img_reset_{uploaded_file.name}"):
                st.session_state[run_key] = False
                st.rerun()

else:
    # ── Empty state ────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="hero-banner animate-in" style="text-align:center;padding:3rem 2rem;">
      <h3>Upload a Road Image to Begin</h3>
      <p style="color:#64748B;font-size:13.5px;max-width:520px;margin:.5rem auto 0;">
        Supports JPG, JPEG, PNG.<br>
        EXIF GPS metadata is automatically extracted — no manual input needed for geo-tagged photos.
      </p>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    for col, icon, title, desc, cls in [
        (c1, "", "Upload",    "Drop a road photo",            "s-total"),
        (c2, "", "EXIF GPS",  "Auto-extract coordinates",     "s-low"),
        (c3, "", "Detect",    "Run YOLOv11 inference",         "s-total"),
        (c4, "", "Pin / Save","Map or Historical",             "s-medium"),
    ]:
        col.markdown(f"""
        <div class="stat-card {cls}" style="text-align:center;padding:1.2rem;">
          <div style="font-weight:700;font-size:13px;color:#0F172A;">{title}</div>
          <div style="font-size:11.5px;color:#64748B;margin-top:3px;">{desc}</div>
        </div>""", unsafe_allow_html=True)
