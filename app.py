"""
Golf Tracker — main entry point.
Handles login and redirects to the home dashboard.
"""
import streamlit as st
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth

st.set_page_config(
    page_title="Golf Tracker",
    page_icon="⛳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Auth ───────────────────────────────────────────────────────────────────────
with open("config.yaml") as f:
    config = yaml.load(f, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"],
)

name, auth_status, username = authenticator.login("Login", "main")

if auth_status is False:
    st.error("Incorrect username or password.")
    st.stop()

if auth_status is None:
    st.info("Please log in to continue.")
    st.stop()

# Store in session for pages to access
st.session_state["username"] = username
st.session_state["name"] = name

# ── Sidebar logout ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"**Logged in as:** {name}")
    authenticator.logout("Logout", "sidebar")

# ── Home page ──────────────────────────────────────────────────────────────────
st.title("⛳ Golf Tracker")
st.markdown(f"Welcome back, **{name}**! Use the sidebar to navigate.")

st.markdown("---")

col1, col2, col3 = st.columns(3)
with col1:
    st.page_link("pages/1_Data_Entry.py", label="📝 Enter a Round", use_container_width=True)
with col2:
    st.page_link("pages/2_Last_Round.py", label="📊 Last Round Stats", use_container_width=True)
with col3:
    st.page_link("pages/3_Summary.py", label="📈 Season Summary", use_container_width=True)
