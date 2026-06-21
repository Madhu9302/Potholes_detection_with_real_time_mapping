import streamlit as st
import re
from database import db_manager

db_manager.init_db()

# ── Load CSS (UTF-8 safe) ─────────────────────────────────────────────────────
try:
    with open("assets/style.css", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    pass

st.markdown("""
<style>
[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ── Auth page layout ───────────────────────────────────────────────────────────
st.markdown("""
<div class="auth-container">
  <div class="auth-logo animate-in">
    <h1 style="font-size:1.75rem!important;margin:0!important;">
      <span class="gradient-text">PotholeAI</span>
    </h1>
    <p style="color:#64748B;font-size:13.5px;margin-top:6px;">
      AI-Powered Infrastructure Monitoring &amp; Safety Navigation
    </p>
  </div>
  <div class="auth-card animate-in delay-1">
""", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["Sign In", "Create Account"])

with tab1:
    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
    login_user = st.text_input("Username", key="login_username", placeholder="your_username")
    login_pass = st.text_input("Password", type="password", key="login_password", placeholder="••••••••")
    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
    if st.button("Sign In →", use_container_width=True, key="signin_btn"):
        if not login_user or not login_pass:
            st.error("Please fill in all fields.")
        else:
            user = db_manager.authenticate_user(login_user, login_pass)
            if user:
                st.session_state.logged_in = True
                st.session_state.user = user
                st.toast(f"Welcome back, {user['username']}!")
                st.rerun()
            else:
                st.error("Invalid username or password.")
    st.markdown(
        '<p style="font-size:12px;color:#334155;text-align:center;margin-top:10px">'
        'Default credentials: <b style="color:#475569">admin</b> / <b style="color:#475569">admin123</b></p>',
        unsafe_allow_html=True
    )

with tab2:
    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
    reg_user    = st.text_input("Username",         key="reg_username",         placeholder="Choose a username")
    reg_email   = st.text_input("Email Address",    key="reg_email",            placeholder="you@example.com")
    reg_pass    = st.text_input("Password",         type="password", key="reg_password",         placeholder="Min. 6 characters")
    reg_confirm = st.text_input("Confirm Password", type="password", key="reg_confirm_password", placeholder="Repeat password")
    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
    if st.button("Create Account →", use_container_width=True, key="register_btn"):
        if not reg_user or not reg_email or not reg_pass or not reg_confirm:
            st.error("All fields are required.")
        elif reg_pass != reg_confirm:
            st.error("Passwords do not match.")
        elif len(reg_pass) < 6:
            st.error("Password must be at least 6 characters.")
        elif not re.match(r"[^@]+@[^@]+\.[^@]+", reg_email):
            st.error("Please enter a valid email address.")
        else:
            success, msg = db_manager.register_user(reg_user, reg_email, reg_pass)
            if success:
                st.success("Account created! Sign in using the tab above.")
            else:
                st.error(msg or "Registration failed.")

st.markdown('</div>', unsafe_allow_html=True)
st.markdown("""
<div class="auth-footer animate-in delay-2">
  PotholeAI Platform &nbsp;·&nbsp; Enterprise Edition &nbsp;·&nbsp; v3.0
</div>
""", unsafe_allow_html=True)
