"""
Course Admin — update hole par and distance values for each course.
Only needed once to set up Gullbringa correctly.
"""
import streamlit as st
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth

from db.queries import get_courses, get_holes, update_hole

# ── Auth guard ─────────────────────────────────────────────────────────────────
with open("config.yaml") as f:
    config = yaml.load(f, Loader=SafeLoader)
authenticator = stauth.Authenticate(
    config["credentials"], config["cookie"]["name"],
    config["cookie"]["key"], config["cookie"]["expiry_days"],
)
_, auth_status, username = authenticator.login("Login", "main")
if not auth_status:
    st.warning("Please log in from the Home page.")
    st.stop()

with st.sidebar:
    st.markdown(f"**Logged in as:** {st.session_state.get('name', username)}")
    authenticator.logout("Logout", "sidebar")

# ── Page ───────────────────────────────────────────────────────────────────────
st.title("⚙️ Course Admin")
st.info("Update the par and distance for each hole. Changes take effect immediately.")

courses = get_courses()
if not courses:
    st.error("No courses found. Run setup_db.py first.")
    st.stop()

course_names = [c["name"] for c in courses]
selected_name = st.selectbox("Course", course_names)
course = next(c for c in courses if c["name"] == selected_name)
holes = get_holes(int(course["id"]))

if not holes:
    st.warning("No holes found for this course.")
    st.stop()

st.subheader(f"{selected_name} — 18 Holes")
st.markdown("Edit par and distance for each hole, then click **Save All Changes**.")

# Build editable form
updated = {}
cols_per_row = 3
rows = [holes[i:i+cols_per_row] for i in range(0, len(holes), cols_per_row)]

for row in rows:
    cols = st.columns(cols_per_row)
    for col, hole in zip(cols, row):
        with col:
            st.markdown(f"**Hole {hole['hole_number']}**")
            par_val = st.selectbox(
                "Par", [3, 4, 5],
                index=[3, 4, 5].index(int(hole["par"])),
                key=f"par_{hole['id']}",
            )
            dist_val = st.number_input(
                "Distance (m)",
                min_value=50, max_value=650,
                value=int(hole["distance_meters"]) if hole["distance_meters"] else 300,
                step=5,
                key=f"dist_{hole['id']}",
            )
            updated[hole["id"]] = (par_val, dist_val)

if st.button("Save All Changes", type="primary", use_container_width=True):
    for hole_id, (par, dist) in updated.items():
        update_hole(hole_id, par, dist)
    st.success("All holes updated!")
    st.rerun()

# ── Preview table ──────────────────────────────────────────────────────────────
import pandas as pd
df = pd.DataFrame([
    {"Hole": h["hole_number"], "Par": h["par"], "Distance (m)": h["distance_meters"]}
    for h in holes
])
st.dataframe(df, use_container_width=True, hide_index=True)
st.caption(f"Total par: {df['Par'].sum()}")
