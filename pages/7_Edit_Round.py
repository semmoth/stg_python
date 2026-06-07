"""
Edit Round — fix shots in a completed round, one hole at a time.
"""
import streamlit as st

from db.queries import (
    get_rounds, get_round, get_holes, get_hole,
    get_shots_for_hole, delete_shots_for_hole, save_shot,
)
from utils.constants import SURFACES, CLUBS

username = st.session_state.get("username", "stefan")

st.title("✏️ Edit Round")

# ── Round selector ─────────────────────────────────────────────────────────────
rounds = get_rounds(username)
completed = [r for r in rounds if int(r.get("completed", 0)) == 1]

if not completed:
    st.info("No completed rounds to edit.")
    st.stop()

round_options = {}
for r in completed:
    label = f"{r['date']} — {r['course_name']} ({r['tee']})"
    round_options[label] = int(r["id"])

selected_label = st.selectbox("Select round", list(round_options.keys()))
round_id = round_options[selected_label]

# Reset editing state when round changes
if st.session_state.get("_edit_round_id") != round_id:
    st.session_state["_edit_round_id"] = round_id
    st.session_state["_edit_hole"] = None
    st.session_state["_edit_shots"] = []
    st.session_state["_editing"] = False

round_info = get_round(round_id)
holes = get_holes(int(round_info["course_id"]), tee_name=round_info["tee"])

# ════════════════════════════════════════════════════════════════════════════════
# VIEW: Hole overview
# ════════════════════════════════════════════════════════════════════════════════
if not st.session_state.get("_editing"):
    st.subheader("Select a hole to edit")

    for hole in holes:
        hn = int(hole["hole_number"])
        par = int(hole["par"])
        existing = get_shots_for_hole(round_id, hn)
        score = len(existing)
        svp = score - par
        svp_str = f"+{svp}" if svp > 0 else str(svp)
        color = "🔴" if svp > 0 else ("🟢" if svp < 0 else "⚪")

        c_hole, c_par, c_score, c_btn = st.columns([1, 1, 2, 1])
        c_hole.write(f"**Hole {hn}**")
        c_par.write(f"Par {par}")
        c_score.write(f"{color} {score} shots ({svp_str})")
        if c_btn.button("Edit", key=f"edit_{hn}"):
            st.session_state["_edit_hole"] = hn
            st.session_state["_edit_shots"] = []
            st.session_state["_editing"] = True
            st.rerun()

    st.stop()

# ════════════════════════════════════════════════════════════════════════════════
# VIEW: Shot entry for selected hole
# ════════════════════════════════════════════════════════════════════════════════
hole_num = st.session_state["_edit_hole"]
hole_info = get_hole(int(round_info["course_id"]), hole_num, tee_name=round_info["tee"])
par = int(hole_info["par"]) if hole_info else 4
hole_dist = hole_info["distance"] if hole_info else "?"

st.subheader(f"Editing Hole {hole_num} — Par {par} — {hole_dist} m")

existing_shots = get_shots_for_hole(round_id, hole_num)
with st.expander("Current shots (will be replaced on save)", expanded=False):
    for s in sorted(existing_shots, key=lambda x: int(x["shot_number"])):
        dist_label = f"{s['distance_to_hole']} ft" if s["distance_unit"] == "feet" else f"{s['distance_to_hole']} m"
        st.write(f"Shot {s['shot_number']}: {s['surface']} | {dist_label} to hole | {s.get('club') or '—'}")

st.markdown("---")

edit_shots: list[dict] = st.session_state["_edit_shots"]

if edit_shots:
    st.markdown("**Shots entered:**")
    for s in edit_shots:
        dist_label = f"{s['distance_to_hole']} ft" if s["distance_unit"] == "feet" else f"{s['distance_to_hole']} m"
        holed_label = " ✅ Holed" if s.get("holed") else ""
        penalty_label = " ⚠️ Penalty" if s.get("penalty") else ""
        st.markdown(
            f"**Shot {s['shot_number']}** — {s['surface']} | {dist_label} | {s.get('club') or '—'}"
            f"{holed_label}{penalty_label}"
        )
    st.markdown("---")

already_holed = edit_shots and edit_shots[-1].get("holed", False)
shot_number = len(edit_shots) + 1

if not already_holed:
    st.subheader(f"Shot {shot_number}")

    if shot_number == 1:
        surface = "Tee"
        st.markdown("**Surface:** Tee (automatic)")
        distance = st.number_input(
            "Distance to hole (meters)", min_value=1, max_value=600,
            value=int(hole_dist) if hole_dist and hole_dist != "?" else 150,
            step=1, key="edit_dist_1",
        )
        club = st.radio("Club", CLUBS, key="edit_club_1", horizontal=True)
        holed = st.checkbox("Holed ✅", key="edit_holed_1")
        penalty = st.checkbox("Penalty shot", key="edit_pen_1")
        distance_unit = "meters"
    else:
        non_tee = [s for s in SURFACES if s != "Tee"]
        surface = st.radio("Surface", non_tee, key=f"edit_surf_{shot_number}", horizontal=True)

        if surface == "Green":
            distance_unit = "feet"
            distance = st.number_input(
                "Remaining distance (feet)", min_value=1, max_value=200,
                value=None, step=1, key=f"edit_dist_{shot_number}",
            )
            club = "Putter"
            st.markdown("**Club:** Putter (automatic)")
        else:
            distance_unit = "meters"
            distance = st.number_input(
                "Remaining distance (meters)", min_value=1, max_value=600,
                value=None, step=1, key=f"edit_dist_{shot_number}",
            )
            club = st.radio("Club", CLUBS, key=f"edit_club_{shot_number}", horizontal=True)

        holed = st.checkbox("Holed ✅", key=f"edit_holed_{shot_number}")
        penalty = st.checkbox("Penalty shot", key=f"edit_pen_{shot_number}")

    if st.button(f"Add Shot {shot_number}", type="primary", use_container_width=True):
        new_shot = {
            "shot_number": shot_number,
            "surface": surface,
            "distance_to_hole": int(distance) if distance is not None else None,
            "distance_unit": distance_unit,
            "club": club,
            "holed": holed,
            "penalty": penalty,
        }
        st.session_state["_edit_shots"].append(new_shot)
        if penalty:
            replay = new_shot.copy()
            replay["shot_number"] = shot_number + 1
            replay["penalty"] = False
            st.session_state["_edit_shots"].append(replay)
        st.rerun()

st.markdown("---")

col_save, col_clear, col_cancel = st.columns(3)

with col_save:
    can_save = len(edit_shots) > 0
    if st.button("💾 Save Changes", disabled=not can_save, type="primary", use_container_width=True):
        delete_shots_for_hole(round_id, hole_num)
        for s in edit_shots:
            save_shot(
                round_id=round_id,
                hole_number=hole_num,
                shot_number=s["shot_number"],
                surface=s["surface"],
                distance_to_hole=s["distance_to_hole"],
                distance_unit=s["distance_unit"],
                club=s.get("club"),
                holed=s.get("holed", False),
                penalty=s.get("penalty", False),
            )
        st.session_state["_edit_shots"] = []
        st.session_state["_edit_hole"] = None
        st.session_state["_editing"] = False
        st.success(f"Hole {hole_num} updated!")
        st.rerun()

with col_clear:
    if st.button("🗑️ Clear Shots", use_container_width=True):
        st.session_state["_edit_shots"] = []
        st.rerun()

with col_cancel:
    if st.button("← Back to Holes", use_container_width=True):
        st.session_state["_edit_shots"] = []
        st.session_state["_edit_hole"] = None
        st.session_state["_editing"] = False
        st.rerun()
