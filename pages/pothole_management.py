import streamlit as st
import pandas as pd
from datetime import datetime
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
  <h1>🔧 <span class="gradient-text">Pothole Management</span></h1>
  <p class="page-subtitle">Review, resolve, and restore pothole records.
  Resolved potholes are hidden from the Live Map and excluded from Route Planner scoring.</p>
</div>""", unsafe_allow_html=True)

# ── KPI row ────────────────────────────────────────────────────────────────────
ms = db_manager.get_pothole_map_stats()
st.markdown(f"""
<div class="kpi-grid animate-in delay-1" style="grid-template-columns:repeat(4,1fr);margin-bottom:1.5rem;">
  <div class="kpi-card">
    <span class="icon">📍</span>
    <div class="kpi-title">Total Potholes</div>
    <div class="kpi-value">{ms['total']}</div>
  </div>
  <div class="kpi-card">
    <span class="icon">🟢</span>
    <div class="kpi-title">Active</div>
    <div class="kpi-value" style="color:#34D399;">{ms['active']}</div>
  </div>
  <div class="kpi-card">
    <span class="icon">✅</span>
    <div class="kpi-title">Resolved</div>
    <div class="kpi-value" style="color:#94A3B8;">{ms['resolved']}</div>
  </div>
  <div class="kpi-card">
    <span class="icon">📊</span>
    <div class="kpi-title">Resolution Rate</div>
    <div class="kpi-value" style="color:#22D3EE;">{ms['resolution_rate']}%</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Load all potholes ──────────────────────────────────────────────────────────
all_ph = db_manager.get_all_potholes()
if not all_ph:
    st.info("No pothole records found. Run detection scans to populate the database.")
    st.stop()

df = pd.DataFrame(all_ph)
df["timestamp"] = pd.to_datetime(df["timestamp"])

# ── Filters ────────────────────────────────────────────────────────────────────
st.markdown('<h3 style="margin-bottom:.75rem;">🔍 Filter & Search</h3>', unsafe_allow_html=True)
fc1, fc2, fc3, fc4 = st.columns(4)
with fc1:
    status_filter = st.selectbox("Status", ["All", "Active", "Resolved"])
with fc2:
    sev_filter = st.multiselect("Severity", ["High", "Medium", "Low"],
                                 default=["High", "Medium", "Low"])
with fc3:
    src_filter = st.multiselect("Source",
        ["Historical", "Image Detection", "Video Detection", "Live Camera",
         "EXIF GPS", "GPX Video", "Manual Location"],
        default=["Historical", "Image Detection", "Video Detection", "Live Camera",
                 "EXIF GPS", "GPX Video", "Manual Location"])
with fc4:
    sort_by = st.selectbox("Sort By", ["Newest First", "Oldest First", "Severity"])

fdf = df.copy()
if status_filter != "All":
    fdf = fdf[fdf["status"] == status_filter]
if sev_filter:
    fdf = fdf[fdf["severity"].isin(sev_filter)]
if src_filter:
    fdf = fdf[fdf["source_type"].isin(src_filter)]
if sort_by == "Newest First":
    fdf = fdf.sort_values("timestamp", ascending=False)
elif sort_by == "Oldest First":
    fdf = fdf.sort_values("timestamp", ascending=True)
elif sort_by == "Severity":
    sev_order = {"High": 0, "Medium": 1, "Low": 2}
    fdf["sev_rank"] = fdf["severity"].map(sev_order)
    fdf = fdf.sort_values("sev_rank").drop(columns=["sev_rank"])

st.markdown(f'<p style="color:#64748B;font-size:13px;margin-bottom:1rem;">Showing <b style="color:#F0F4FF">{len(fdf)}</b> records</p>',
            unsafe_allow_html=True)

# ── Confirmation state ─────────────────────────────────────────────────────────
if "mgmt_confirm_id" not in st.session_state:
    st.session_state.mgmt_confirm_id = None
if "mgmt_confirm_action" not in st.session_state:
    st.session_state.mgmt_confirm_action = None

# ── Confirmation dialog ────────────────────────────────────────────────────────
if st.session_state.mgmt_confirm_id is not None:
    cid    = st.session_state.mgmt_confirm_id
    action = st.session_state.mgmt_confirm_action
    row    = df[df["id"] == cid].iloc[0]

    action_label = "Mark as Resolved" if action == "Resolved" else "Restore as Active"
    action_color = "#94A3B8" if action == "Resolved" else "#34D399"
    action_icon  = "✅" if action == "Resolved" else "🔄"

    st.markdown(f"""
    <div style="background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.35);
                border-radius:14px;padding:1.25rem 1.5rem;margin-bottom:1.5rem;">
      <h4 style="margin:0 0 8px;color:#FCD34D;">⚠️ Confirm Action</h4>
      <p style="color:#94A3B8;font-size:13.5px;margin:0 0 4px;">
        Pothole <b style="color:#F0F4FF;">#{cid}</b> — {row['severity']} Severity · {row['source_type']}<br>
        📍 {row['latitude']:.6f}, {row['longitude']:.6f}
      </p>
    </div>""", unsafe_allow_html=True)

    if action == "Resolved":
        st.markdown('<p style="color:#94A3B8;font-size:13.5px;font-weight:600;">Has this pothole been repaired?</p>',
                    unsafe_allow_html=True)

    remarks = st.text_input(
        "Remarks (optional)",
        placeholder="e.g. Road repaired, False detection, Temporary fix...",
        key="mgmt_remarks"
    )

    ca, cb, _ = st.columns([1, 1, 3])
    with ca:
        if st.button(f"{action_icon} Confirm — {action_label}", use_container_width=True):
            ok = db_manager.set_pothole_status(cid, action, remarks)
            if ok:
                st.success(f"✅ Pothole #{cid} marked as **{action}**.")
                st.toast(f"#{cid} → {action}", icon=action_icon)
            else:
                st.error("Failed to update status.")
            st.session_state.mgmt_confirm_id     = None
            st.session_state.mgmt_confirm_action = None
            st.rerun()
    with cb:
        if st.button("✕ Cancel", use_container_width=True, type="secondary"):
            st.session_state.mgmt_confirm_id     = None
            st.session_state.mgmt_confirm_action = None
            st.rerun()

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

# ── Pothole records table ──────────────────────────────────────────────────────
st.markdown('<h3 style="margin-bottom:.75rem;">📋 Pothole Records</h3>', unsafe_allow_html=True)

for _, row in fdf.iterrows():
    pid       = int(row["id"])
    sev       = row["severity"]
    src       = row.get("source_type", "Historical")
    status    = row.get("status", "Active")
    remarks   = row.get("remarks", "") or ""
    ts        = row["timestamp"].strftime("%Y-%m-%d %H:%M")
    lat       = float(row["latitude"])
    lon       = float(row["longitude"])
    conf      = float(row["confidence"])

    pill_cls  = {"High": "pill-high", "Medium": "pill-medium", "Low": "pill-low"}.get(sev, "pill-low")
    st_badge  = (
        '<span class="badge badge-green" style="font-size:11px;">🟢 Active</span>'
        if status == "Active" else
        '<span class="badge" style="background:rgba(100,116,139,.15);color:#94A3B8;border:1px solid rgba(100,116,139,.25);font-size:11px;">✅ Resolved</span>'
    )
    remarks_html = (
        f'<span style="color:#64748B;font-size:11.5px;">📝 {remarks}</span><br>'
        if remarks else ""
    )

    col_info, col_btn = st.columns([5, 1])
    with col_info:
        st.markdown(f"""
        <div class="stat-card {'s-low' if status=='Active' else ''}"
             style="opacity:{'1' if status=='Active' else '0.65'};">
          <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:4px;">
            <b style="color:#F0F4FF;">#{pid}</b>
            <span class="det-pill {pill_cls}">{sev}</span>
            {st_badge}
            <span class="badge badge-cyan" style="font-size:10.5px;">{src}</span>
          </div>
          <div style="font-size:12.5px;color:#94A3B8;line-height:1.8;">
            📍 {lat:.6f}, {lon:.6f} &nbsp;·&nbsp; 📊 {conf:.0%} &nbsp;·&nbsp; 🕐 {ts}<br>
            {remarks_html}
          </div>
        </div>""", unsafe_allow_html=True)

    with col_btn:
        st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
        if status == "Active":
            if st.button("✅ Resolve", key=f"resolve_{pid}", use_container_width=True):
                st.session_state.mgmt_confirm_id     = pid
                st.session_state.mgmt_confirm_action = "Resolved"
                st.rerun()
        else:
            if st.button("🔄 Restore", key=f"restore_{pid}", use_container_width=True,
                         type="secondary"):
                st.session_state.mgmt_confirm_id     = pid
                st.session_state.mgmt_confirm_action = "Active"
                st.rerun()

# ── Export ─────────────────────────────────────────────────────────────────────
st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
e1, e2 = st.columns(2)
export_df = fdf.copy()
export_df["timestamp"] = export_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
with e1:
    st.download_button("⬇️ Export CSV", export_df.to_csv(index=False).encode("utf-8"),
                       "potholes_management.csv", "text/csv", use_container_width=True)
with e2:
    st.download_button("⬇️ Export JSON",
                       export_df.to_json(orient="records", date_format="iso").encode("utf-8"),
                       "potholes_management.json", "application/json", use_container_width=True)
