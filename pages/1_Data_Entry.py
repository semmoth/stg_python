"""
Hole-by-hole data entry page.

Flow:
  1. Start a new round (select date, course, tee).
  2. For each hole 1-18:
       - Shot 1 is always Tee. Enter distance to hole (meters).
       - Each additional shot: choose surface, enter distance, choose club
         (auto Putter on Green), optionally enter shot distance, tick "Holed".
  3. Save hole → move to next. After hole 18 → round is complete.
"""
import streamlit as st
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
from datetime import date

from db.queries import (
    get_courses, get_holes, get_hole,
    create_round, complete_round, delete_round,
    save_shot, get_shots_for_hole, delete_shots_for_hole,
)
from utils.constants import SURFACES, CLUBS, TEES

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

# ── Session state initialisation ───────────────────────────────────────────────
for key, default in [
    ("round_id", None),
    ("current_hole", 1),
    ("hole_shots", []),   # list of shot dicts for the hole being entered
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Page ───────────────────────────────────────────────────────────────────────
st.title("📝 Enter a Round")

# ════════════════════════════════════════════════════════════════════════════════
# SECTION A — Start a new round
# ════════════════════════════════════════════════════════════════════════════════
if st.session_state.round_id is None:
    st.subheader("Start a new round")

    courses = get_courses()
    if not courses:
        st.error("No courses found. Run setup_db.py first.")
        st.stop()

    course_names = [c["name"] for c in courses]
    selected_course_name = st.selectbox("Course", course_names)
    course = next(c for c in courses if c["name"] == selected_course_name)

    col1, col2 = st.columns(2)
    with col1:
        round_date = st.date_input("Date", value=date.today())
    with col2:
        tee = st.selectbox("Tee", TEES)

    if st.button("Start Round ⛳", type="primary", use_container_width=True):
        round_id = create_round(
            username=username,
            course_id=int(course["id"]),
            date=str(round_date),
            tee=tee,
        )
        st.session_state.round_id = round_id
        st.session_state.current_hole = 1
        st.session_state.hole_shots = []
        st.rerun()

    st.stop()

# ════════════════════════════════════════════════════════════════════════════════
# SECTION B — Hole-by-hole entry
# ════════════════════════════════════════════════════════════════════════════════
round_id = st.session_state.round_id
current_hole = st.session_state.current_hole

if current_hole > 18:
    # ── Round complete ─────────────────────────────────────────────────────────
    st.success("🏁 Round complete! All 18 holes saved.")
    complete_round(round_id)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("View Last Round Stats →", use_container_width=True):
            st.session_state.round_id = None
            st.session_state.current_hole = 1
            st.session_state.hole_shots = []
            st.switch_page("pages/2_Last_Round.py")
    with col2:
        if st.button("Start Another Round", use_container_width=True):
            st.session_state.round_id = None
            st.session_state.current_hole = 1
            st.session_state.hole_shots = []
            st.rerun()
    st.stop()

# ── Get hole info from DB ──────────────────────────────────────────────────────
round_info = None
from db.queries import get_round
round_info = get_round(round_id)
course_id = int(round_info["course_id"]) if round_info else None
hole_info = get_hole(course_id, current_hole) if course_id else None
par = int(hole_info["par"]) if hole_info else 4
hole_dist = hole_info["distance_meters"] if hole_info else "?"

# ── Header ─────────────────────────────────────────────────────────────────────
progress = (current_hole - 1) / 18
st.progress(progress, text=f"Hole {current_hole} of 18")

col_h, col_p, col_d = st.columns(3)
col_h.metric("Hole", current_hole)
col_p.metric("Par", par)
col_d.metric("Distance", f"{hole_dist} m" if hole_dist else "—")

st.markdown("---")

# ── Shots already entered for this hole ───────────────────────────────────────
hole_shots: list[dict] = st.session_state.hole_shots

if hole_shots:
    st.markdown("**Shots entered:**")
    for s in hole_shots:
        surface = s["surface"]
        dist = s["distance_to_hole"]
        unit = s["distance_unit"]
        club = s.get("club") or ("Putter" if surface == "Green" else "—")
        shot_dist = s.get("shot_distance")
        holed = s.get("holed", False)

        dist_label = f"{dist} ft" if unit == "feet" else f"{dist} m"
        shot_dist_label = f" | shot {shot_dist} m" if shot_dist else ""
        holed_label = " ✅ Holed" if holed else ""
        st.markdown(
            f"**Shot {s['shot_number']}** — {surface} | {dist_label} to hole"
            f" | {club}{shot_dist_label}{holed_label}"
        )
    st.markdown("---")

# ── Check if hole is already holed ────────────────────────────────────────────
already_holed = hole_shots and hole_shots[-1].get("holed", False)

# ── Add a new shot ─────────────────────────────────────────────────────────────
shot_number = len(hole_shots) + 1

if not already_holed:
    st.subheader(f"Shot {shot_number}")

    if shot_number == 1:
        # First shot always from tee
        surface = "Tee"
        st.markdown(f"**Surface:** Tee (automatic)")
        distance = st.number_input(
            "Distance to hole (meters)", min_value=1, max_value=600,
            value=int(hole_dist) if hole_dist and hole_dist != "?" else 150,
            step=1, key="dist_input",
        )
        club = None
        shot_dist_val = st.number_input(
            "Shot distance (meters) — optional, for driving stats",
            min_value=0, max_value=400, value=0, step=1, key="shot_dist_input",
        )
        shot_dist_val = float(shot_dist_val) if shot_dist_val > 0 else None
        holed = st.checkbox("Holed ✅", key="holed_check")
        distance_unit = "meters"

    else:
        # Subsequent shots
        non_tee_surfaces = [s for s in SURFACES if s != "Tee"]
        surface = st.selectbox("Surface", non_tee_surfaces, key="surface_select")

        if surface == "Green":
            distance_unit = "feet"
            distance = st.number_input(
                "Distance to hole (feet)", min_value=1, max_value=200,
                value=10, step=1, key="dist_input",
            )
            club = "Putter"
            st.markdown("**Club:** Putter (automatic)")
            shot_dist_val = None
        else:
            distance_unit = "meters"
            distance = st.number_input(
                "Distance to hole (meters)", min_value=1, max_value=600,
                value=100, step=1, key="dist_input",
            )
            club = st.selectbox("Club", CLUBS, key="club_select")
            shot_dist_val = st.number_input(
                "Shot distance (meters) — optional",
                min_value=0, max_value=400, value=0, step=1, key="shot_dist_input",
            )
            shot_dist_val = float(shot_dist_val) if shot_dist_val > 0 else None

        holed = st.checkbox("Holed ✅", key="holed_check")

    # ── Add shot button ────────────────────────────────────────────────────────
    if st.button(f"Add Shot {shot_number}", type="primary", use_container_width=True):
        new_shot = {
            "shot_number": shot_number,
            "surface": surface,
            "distance_to_hole": float(distance),
            "distance_unit": distance_unit,
            "club": club,
            "shot_distance": shot_dist_val,
            "holed": holed,
        }
        st.session_state.hole_shots.append(new_shot)
        st.rerun()

st.markdown("---")

# ── Save hole and proceed ──────────────────────────────────────────────────────
col_save, col_redo = st.columns(2)

with col_save:
    label = "Save Hole & Next →" if current_hole < 18 else "Save Hole & Finish Round 🏁"
    can_save = len(hole_shots) > 0

    if st.button(label, disabled=not can_save, type="primary", use_container_width=True):
        # Delete any previously saved shots for this hole (in case of re-entry)
        delete_shots_for_hole(round_id, current_hole)
        # Save all shots to DB
        for s in hole_shots:
            save_shot(
                round_id=round_id,
                hole_number=current_hole,
                shot_number=s["shot_number"],
                surface=s["surface"],
                distance_to_hole=s["distance_to_hole"],
                distance_unit=s["distance_unit"],
                club=s.get("club"),
                shot_distance=s.get("shot_distance"),
                holed=s.get("holed", False),
            )
        # Advance to next hole
        st.session_state.current_hole = current_hole + 1
        st.session_state.hole_shots = []
        st.rerun()

with col_redo:
    if st.button("Redo This Hole", use_container_width=True):
        st.session_state.hole_shots = []
        st.rerun()

# ── Abandon round ──────────────────────────────────────────────────────────────
with st.expander("⚠️ Abandon this round"):
    st.warning("This will permanently delete all data entered for this round.")
    if st.button("Delete round and start over", type="secondary"):
        delete_round(round_id)
        st.session_state.round_id = None
        st.session_state.current_hole = 1
        st.session_state.hole_shots = []
        st.rerun()
