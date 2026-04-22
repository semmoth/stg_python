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
from utils.constants import SURFACES, CLUBS, TEES, TEES_ID, CLUB_DISTANCE_ESTIMATES

# ── Auth guard ─────────────────────────────────────────────────────────────────
# TODO: Re-enable authentication when config is fixed
# with open("config.yaml") as f:
#     config = yaml.load(f, Loader=SafeLoader)
# authenticator = stauth.Authenticate(
#     config["credentials"], config["cookie"]["name"],
#     config["cookie"]["key"], config["cookie"]["expiry_days"],
# )
# _, auth_status, username = authenticator.login(location="unrendered")
# if not auth_status:
#     st.warning("Please log in from the Home page.")
#     st.stop()

# Use session state values set from app.py
username = st.session_state.get("username", "dev")
name = st.session_state.get("name", "Developer")

# ── Session state initialisation ───────────────────────────────────────────────
for key, default in [
    ("round_id", None),
    ("current_hole", 1),
    ("hole_shots", []),   # list of shot dicts for the hole being entered
    ("total_holes", 18),  # number of holes in the course
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
        # Get total holes for this course
        holes = get_holes(int(course["id"]), TEES_ID[tee])
        st.session_state.total_holes = len(holes)
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
total_holes = st.session_state.total_holes

if current_hole > total_holes:
    # ── Round complete ─────────────────────────────────────────────────────────
    st.success(f"🏁 Round complete! All {total_holes} holes saved.")
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
tee_id = TEES_ID[round_info["tee"]] if round_info else 1
hole_info = get_hole(course_id, current_hole, tee_id) if course_id else None
par = int(hole_info["par"]) if hole_info else 4
hole_dist = hole_info["distance"] if hole_info else "?"

# ── Header ─────────────────────────────────────────────────────────────────────
progress = (current_hole - 1) / total_holes
st.progress(progress, text=f"Hole {current_hole} of {total_holes}")

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
        penalty_label = " ⚠️ Penalty" if s.get("penalty", False) else ""
        st.markdown(
            f"**Shot {s['shot_number']}** — {surface} | {dist_label} to hole"
            f" | {club}{shot_dist_label}{holed_label}{penalty_label}"
        )
    st.markdown("---")

# ── Check if hole is already holed ────────────────────────────────────────────
already_holed = hole_shots and hole_shots[-1].get("holed", False)

# ── Add a new shot ─────────────────────────────────────────────────────────────
shot_number = len(hole_shots) + 1

# Auto-suggest next surface and distance based on prior shot
next_surface = None
next_distance = None
next_club = None
if hole_shots:
    last = hole_shots[-1]
    last_dist = last.get("distance_to_hole")
    last_shot_distance = last.get("shot_distance")
    last_penalty = last.get("penalty", False)

    # Default to Green based on par and shot number
    if shot_number == 2 and par == 3:
        next_surface = "Green"
    elif shot_number == 3 and par == 4:
        next_surface = "Green"
    elif shot_number == 4 and par == 5:
        next_surface = "Green"

    if last_penalty:
        next_distance = last_dist
        next_surface = last.get("surface", "Fairway")
        next_club = last.get("club")
    elif last_dist is not None and last_shot_distance is not None:
        next_distance = max(1, int(last_dist - last_shot_distance))

if not already_holed:
    st.subheader(f"Shot {shot_number}")

    if shot_number == 1:
        # First shot always from tee
        surface = "Tee"
        st.markdown("**Surface:** Tee (automatic)")
        distance = st.number_input(
            "Distance to hole (meters)", min_value=1, max_value=600,
            value=int(hole_dist) if hole_dist and hole_dist != "?" else 150,
            step=1, key="dist_input",
        )
        club = st.selectbox("Club", CLUBS, key="club_select")
        shot_dist_val = st.number_input(
            "Shot distance (meters) — optional, for driving stats",
            min_value=0, max_value=400, value=None, step=1, key="shot_dist_input",
        )
        shot_dist_val = float(shot_dist_val) if shot_dist_val > 0 else None
        holed = st.checkbox("Holed ✅", key="holed_check")
        penalty = st.checkbox("Penalty shot", value=False, key="penalty_check")
        distance_unit = "meters"

    else:
        # Subsequent shots
        non_tee_surfaces = [s for s in SURFACES if s != "Tee"]
        default_surface = next_surface if next_surface in non_tee_surfaces else non_tee_surfaces[0]
        surface = st.selectbox(
            "Surface", non_tee_surfaces,
            index=non_tee_surfaces.index(default_surface),
            key="surface_select",
        )

        if surface == "Green":
            distance_unit = "feet"
            distance = st.number_input(
                "Distance to hole (feet)", min_value=1, max_value=200,
                value=None,
                step=1, key="dist_input",
            )
            club = "Putter"
            st.markdown("**Club:** Putter (automatic)")
            shot_dist_val = None
        else:
            distance_unit = "meters"
            distance = st.number_input(
                "Distance to hole (meters)", min_value=1, max_value=600,
                value=None,
                step=1, key="dist_input",
            )
            suggested_club = next_club or None
            if suggested_club is None and next_distance is not None:
                # pick closest club based on estimate
                candidate = min(CLUB_DISTANCE_ESTIMATES.items(), key=lambda x: abs(x[1] - next_distance))[0]
                suggested_club = candidate
            club_index = CLUBS.index(suggested_club) if suggested_club in CLUBS else 0
            club = st.selectbox("Club", CLUBS, index=club_index, key="club_select")
            shot_dist_val = st.number_input(
                "Shot distance (meters) — optional",
                min_value=0, max_value=600, value=None, step=1, key="shot_dist_input",
            )
            shot_dist_val = float(shot_dist_val) if shot_dist_val > 0 else None

        holed = st.checkbox("Holed ✅", key="holed_check")
        penalty = st.checkbox("Penalty shot", value=False, key="penalty_check")

    # ── Add shot button ────────────────────────────────────────────────────────
    if st.button(f"Add Shot {shot_number}", type="primary", use_container_width=True):
        new_shot = {
            "shot_number": shot_number,
            "surface": surface,
            "distance_to_hole": int(distance) if distance is not None else None,
            "distance_unit": distance_unit,
            "club": club,
            "shot_distance": int(shot_dist_val) if shot_dist_val is not None else None,
            "holed": holed,
            "penalty": penalty,
        }
        st.session_state.hole_shots.append(new_shot)

        if penalty:
            replay_shot = new_shot.copy()
            replay_shot["shot_number"] = shot_number + 1
            replay_shot["penalty"] = False
            st.session_state.hole_shots.append(replay_shot)

        st.rerun()

st.markdown("---")

# ── Save hole and proceed ──────────────────────────────────────────────────────
col_save, col_redo = st.columns(2)

with col_save:
    label = "Save Hole & Next →" if current_hole < total_holes else "Save Hole & Finish Round 🏁"
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
                penalty=s.get("penalty", False),
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
