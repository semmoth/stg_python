"""
Golf Tracker — main entry point.
Authentication is handled by Streamlit Cloud viewer authentication (SSO gate).
"""
import streamlit as st

st.set_page_config(
    page_title="Golf Tracker",
    page_icon="⛳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Identity — single user, auth handled externally by Streamlit Cloud SSO
username = "stefan"
name = "Stefan"

# Store in session for pages to access
st.session_state["username"] = username
st.session_state["name"] = name

# ── Home page ──────────────────────────────────────────────────────────────────
st.title("⛳ Golf Tracker")
st.markdown(f"Welcome back, **{name}**! Use the sidebar to navigate.")

st.markdown("---")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.page_link("pages/1_Data_Entry.py", label="📝 Enter a Round", use_container_width=True)
with col2:
    st.page_link("pages/2_Last_Round.py", label="📊 Last Round Stats", use_container_width=True)
with col3:
    st.page_link("pages/3_Summary.py", label="📈 Season Summary", use_container_width=True)
with col4:
    st.page_link("pages/5_Tournament_Admin.py", label="🏆 Tournament Admin", use_container_width=True)
