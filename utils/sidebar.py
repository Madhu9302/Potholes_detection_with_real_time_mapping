import streamlit as st

def render_sidebar():
    """Call this at the top of every page to render brand + user + logout."""
    with st.sidebar:
        try:
            with open("assets/style.css", encoding="utf-8") as f:
                st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
        except FileNotFoundError:
            pass

        st.markdown("""
        <div class="sidebar-brand">
          <div class="brand-name">PotholeAI</div>
          <div class="brand-sub">Infrastructure Monitoring Platform</div>
        </div>""", unsafe_allow_html=True)

        u = st.session_state.get("user", {})
        if u:
            st.markdown(f"""
            <div class="sidebar-user">
              <div class="uname">{u.get('username','')}</div>
              <div class="uemail">{u.get('email','')}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
        if st.button("Sign Out", use_container_width=True, type="secondary", key="global_signout"):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.toast("Logged out.")
            st.rerun()
