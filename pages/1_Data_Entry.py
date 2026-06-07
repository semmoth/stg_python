"""
Hole-by-hole data entry page.

Flow:
  1. Start a new round (select date, course, tee).
  2. For each hole 1-18:
       - Shot 1 is always Tee. Enter distance to hole (meters).
       - Each additional shot: choose surface, enter distance, choose club
         (auto Putter on Green), tick "Holed".
  3. Save hole → move to next. After hole 18 → round is complete.
"""
import streamlit as st
import pandas as pd
from datetime import date

from db.queries import (
    get_courses, get_course_tee_names, get_holes, get_hole,
    create_round, complete_round, delete_round,
    save_shot, delete_shots_for_hole,
    get_tournaments,
)
from utils.constants import SURFACES, CLUBS, TEES

# ── Quick Entry helpers ────────────────────────────────────────────────────────
_QUICK_CLUBS: dict[str, str] = {
    "D":  "Driver",
    "4W": "4 Wood",
    "2H": "2 Hybrid",
    "4I": "4 Iron",
    "5I": "5 Iron",
    "6I": "6 Iron",
    "7I": "7 Iron",
    "8I": "8 Iron",
    "9I": "9 Iron",
    "PW": "PW",
    "GW": "GW",
    "SW": "SW",
    "LW": "LW",
    "P":  "Putter",
}

def _parse_quick_entry(text: str, tee_distance: int) -> "list[dict] | str":
    """
    Parse a compact hole string like 'D F100 PW G10' into shot dicts.
    Returns a list of shot dicts on success, or an error string on failure.

    Token rules:
      - First token  : club abbreviation (tee shot, surface=Tee, distance from DB)
      - G<dist>      : Green shot, <dist> in feet, club=Putter
      - <surf><dist> : surface + distance in metres (F=Fairway, R=Rough, S=Sand,
                        RC=Recovery); must be immediately followed by a club token
      - Last shot is automatically marked holed=True
    """
    tokens = text.strip().upper().split()
    if not tokens:
        return "Empty entry — type at least a club for the tee shot"

    shots: list[dict] = []
    i, shot_num = 0, 1

    # Token 0: tee shot club
    tee_club = _QUICK_CLUBS.get(tokens[0])
    if tee_club is None:
        return f"Unknown club '{tokens[0]}'. Valid clubs: {' '.join(_QUICK_CLUBS)}"
    shots.append({
        "shot_number": shot_num, "surface": "Tee",
        "distance_to_hole": tee_distance, "distance_unit": "meters",
        "club": tee_club, "holed": False, "penalty": False,
    })
    i, shot_num = 1, 2

    while i < len(tokens):
        tok = tokens[i]

        # Green: G + digits (feet, auto Putter)
        if tok.startswith("G") and tok[1:].isdigit():
            shots.append({
                "shot_number": shot_num, "surface": "Green",
                "distance_to_hole": int(tok[1:]), "distance_unit": "feet",
                "club": "Putter", "holed": False, "penalty": False,
            })
            i, shot_num = i + 1, shot_num + 1
            continue

        # Recovery (check RC before R to avoid prefix clash)
        if tok.startswith("RC") and tok[2:].isdigit():
            surface, dist_str = "Recovery", tok[2:]
        elif tok[:1] in ("F", "R", "S") and tok[1:].isdigit():
            surface = {"F": "Fairway", "R": "Rough", "S": "Sand"}[tok[0]]
            dist_str = tok[1:]
        else:
            return (
                f"Unrecognized token '{tok}'. "
                "Expected surface+distance (F100, R80, S15, RC50) or green (G10)."
            )

        # Next token must be a club
        if i + 1 >= len(tokens):
            return f"Missing club after '{tok}' — add a club code (e.g. PW, 7I)"
        club = _QUICK_CLUBS.get(tokens[i + 1])
        if club is None:
            return f"Unknown club '{tokens[i + 1]}'. Valid clubs: {' '.join(_QUICK_CLUBS)}"

        shots.append({
            "shot_number": shot_num, "surface": surface,
            "distance_to_hole": int(dist_str), "distance_unit": "meters",
            "club": club, "holed": False, "penalty": False,
        })
        i, shot_num = i + 2, shot_num + 1

    if shots:
        shots[-1]["holed"] = True
    return shots


# Use session state values set from app.py
username = st.session_state.get("username", "stefan")
name = st.session_state.get("name", "Stefan")

# ── Session state initialisation ───────────────────────────────────────────────
for key, default in [
    ("round_id", None),
    ("current_hole", 1),
    ("hole_shots", []),   # list of shot dicts for the hole being entered
    ("total_holes", 18),  # number of holes in the course
    ("entry_mode", "Standard"),
    ("qe_parsed", None),
    ("qe_errors", []),
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

    tournaments = get_tournaments()
    tournament_options = ["None"] + [
        f"{t['name']} — {t['course_name']} ({t['tee']}) {t['start_date']} → {t['end_date']}"
        for t in tournaments
    ]
    selected_tournament_option = st.selectbox("Tournament", tournament_options)
    selected_tournament = None
    if selected_tournament_option != "None":
        selected_tournament = tournaments[tournament_options.index(selected_tournament_option) - 1]

    if selected_tournament:
        course = next(c for c in courses if int(c["id"]) == int(selected_tournament["course_id"]))
        st.text_input("Course", course["name"], disabled=True)
        st.text_input("Tee", selected_tournament["tee"], disabled=True)
        round_date = st.date_input(
            "Date",
            value=date.fromisoformat(selected_tournament["start_date"]),
            min_value=date.fromisoformat(selected_tournament["start_date"]),
            max_value=date.fromisoformat(selected_tournament["end_date"]),
        )
        tee = selected_tournament["tee"]
    else:
        course_names = [c["name"] for c in courses]
        selected_course_name = st.selectbox("Course", course_names)
        course = next(c for c in courses if c["name"] == selected_course_name)

        tee_options = get_course_tee_names(int(course["id"]))
        if not tee_options:
            tee_options = TEES

        col1, col2 = st.columns(2)
        with col1:
            round_date = st.date_input("Date", value=date.today())
        with col2:
            tee = st.selectbox("Tee", tee_options)

    entry_mode = st.radio(
        "Entry mode",
        ["Standard", "Quick Entry"],
        horizontal=True,
        help="Quick Entry: type all holes in compact shorthand after starting the round.",
    )

    if st.button("Start Round ⛳", type="primary", use_container_width=True):
        round_id = create_round(
            username=username,
            course_id=int(course["id"]),
            date=str(round_date),
            tee=tee,
            tournament_id=int(selected_tournament["id"]) if selected_tournament else None,
        )
        # Get total holes for this course
        holes = get_holes(int(course["id"]), tee_name=tee)
        st.session_state.total_holes = len(holes)
        st.session_state.round_id = round_id
        st.session_state.current_hole = 1
        st.session_state.hole_shots = []
        st.session_state.entry_mode = entry_mode
        st.session_state.qe_parsed = None
        st.session_state.qe_errors = []
        st.rerun()

    st.stop()

# ════════════════════════════════════════════════════════════════════════════════
# SECTION B — Hole-by-hole entry  /  SECTION C — Quick Entry
# ════════════════════════════════════════════════════════════════════════════════
round_id = st.session_state.round_id
current_hole = st.session_state.current_hole
total_holes = st.session_state.total_holes

# ── Section C: Quick Entry (all holes in compact text format) ──────────────────
if st.session_state.get("entry_mode") == "Quick Entry":
    from db.queries import get_round as _get_round
    _round_info = _get_round(round_id)
    _course_id = int(_round_info["course_id"])
    _holes = get_holes(_course_id, tee_name=_round_info["tee"])

    st.subheader("⚡ Quick Entry")
    st.caption(f"Enter all {len(_holes)} holes below — one line per hole.")

    with st.expander("📖 Format reference", expanded=False):
        _c1, _c2 = st.columns(2)
        with _c1:
            st.markdown("""
**One line per hole.** Tokens separated by spaces.
Lines starting with `#` are ignored.

**Token types:**
- First token = tee shot club (e.g. `D`)
- `F100` = Fairway, 100 m · `R80` = Rough, 80 m
- `S15` = Sand, 15 m · `RC30` = Recovery, 30 m
- `G10` = Green, 10 ft → Putter (auto)

Each surface token **must be followed by a club token.**
The last shot is automatically marked as holed.
""")
        with _c2:
            st.markdown("""
**Club codes:**
`D` Driver · `4W` 4 Wood · `2H` 2 Hybrid
`4I` `5I` `6I` `7I` `8I` `9I` Irons
`PW` · `GW` · `SW` · `LW` · `P` Putter

**Examples:**
- Par 3 birdie: `7I G8`
- Par 4 par: `D F100 PW G10`
- Par 5 bogey: `D F220 7I G25 G5`
- Chip-in: `D R110 SW`
""")

    # Hole reference bar — helps the user count which line is which hole
    _hole_ref = "  ·  ".join(
        f"**{h['hole_number']}** P{h['par']} {h['distance']}m" for h in _holes
    )
    st.caption(_hole_ref)

    _qe_text = st.text_area(
        "Holes (one per line):",
        height=max(360, len(_holes) * 26 + 40),
        key="qe_text",
        placeholder="D F100 PW G10\n7I G15 G4\n...",
    )

    _col_parse, _col_switch = st.columns(2)
    with _col_parse:
        _do_parse = st.button("🔍 Parse & Preview", type="primary", use_container_width=True)
    with _col_switch:
        if st.button("Switch to Standard Entry", use_container_width=True):
            st.session_state.entry_mode = "Standard"
            st.session_state.qe_parsed = None
            st.session_state.qe_errors = []
            st.rerun()

    if _do_parse:
        _lines = [l for l in _qe_text.split("\n") if l.strip() and not l.strip().startswith("#")]
        if len(_lines) != len(_holes):
            st.session_state.qe_errors = [
                f"Expected {len(_holes)} hole entries (one per line), got {len(_lines)}."
            ]
            st.session_state.qe_parsed = None
        else:
            _parsed, _errors = [], []
            for _hole, _line in zip(_holes, _lines):
                _tee_dist = int(_hole["distance"]) if _hole.get("distance") else 150
                _result = _parse_quick_entry(_line, _tee_dist)
                if isinstance(_result, str):
                    _errors.append(f"Hole {_hole['hole_number']}: {_result}")
                else:
                    _parsed.append((_hole, _result))
            if _errors:
                st.session_state.qe_errors = _errors
                st.session_state.qe_parsed = None
            else:
                st.session_state.qe_parsed = _parsed
                st.session_state.qe_errors = []
        st.rerun()

    for _err in st.session_state.get("qe_errors", []):
        st.error(_err)

    _parsed_data = st.session_state.get("qe_parsed")
    if _parsed_data:
        st.subheader("Preview")
        _rows = []
        for _hole, _shot_list in _parsed_data:
            _par = int(_hole["par"])
            _score = len(_shot_list)
            _diff = _score - _par
            _putts = sum(1 for s in _shot_list if s["surface"] == "Green")
            _rows.append({
                "Hole": int(_hole["hole_number"]),
                "Par": _par,
                "Score": _score,
                "+/-": f"+{_diff}" if _diff > 0 else str(_diff),
                "Putts": _putts,
                "Shots": " → ".join(
                    f"{s['surface'][0]}({s['club'][:2]})" for s in _shot_list
                ),
            })
        st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True)

        _total_score = sum(len(sl) for _, sl in _parsed_data)
        _total_par = sum(int(h["par"]) for h, _ in _parsed_data)
        _diff = _total_score - _total_par
        st.markdown(f"**Total: {_total_score} ({'+' if _diff > 0 else ''}{_diff})**")

        if st.button("✅ Save All & Complete Round", type="primary", use_container_width=True):
            for _hole, _shot_list in _parsed_data:
                _hole_num = int(_hole["hole_number"])
                delete_shots_for_hole(round_id, _hole_num)
                for s in _shot_list:
                    save_shot(
                        round_id=round_id,
                        hole_number=_hole_num,
                        shot_number=s["shot_number"],
                        surface=s["surface"],
                        distance_to_hole=s["distance_to_hole"],
                        distance_unit=s["distance_unit"],
                        club=s.get("club"),
                        holed=s.get("holed", False),
                        penalty=s.get("penalty", False),
                    )
            complete_round(round_id)
            for _k in ("round_id", "current_hole", "hole_shots", "entry_mode", "qe_parsed", "qe_errors"):
                st.session_state.pop(_k, None)
            st.switch_page("pages/2_Last_Round.py")

    with st.expander("⚠️ Abandon this round"):
        st.warning("This will permanently delete all data entered for this round.")
        if st.button("Delete round and start over", type="secondary", key="qe_abandon"):
            delete_round(round_id)
            for _k in ("round_id", "current_hole", "hole_shots", "entry_mode", "qe_parsed", "qe_errors"):
                st.session_state.pop(_k, None)
            st.rerun()

    st.stop()

# ── Section B continues: Standard hole-by-hole entry ──────────────────────────
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
from db.queries import get_round
round_info = get_round(round_id)
course_id = int(round_info["course_id"]) if round_info else None
hole_info = get_hole(course_id, current_hole, tee_name=round_info["tee"]) if course_id else None
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
        holed = s.get("holed", False)

        dist_label = f"{dist} ft" if unit == "feet" else f"{dist} m"
        holed_label = " ✅ Holed" if holed else ""
        penalty_label = " ⚠️ Penalty" if s.get("penalty", False) else ""
        st.markdown(
            f"**Shot {s['shot_number']}** — {surface} | {dist_label} to hole"
            f" | {club}{holed_label}{penalty_label}"
        )
    st.markdown("---")

# ── Check if hole is already holed ────────────────────────────────────────────
already_holed = hole_shots and hole_shots[-1].get("holed", False)

# ── Add a new shot ─────────────────────────────────────────────────────────────
shot_number = len(hole_shots) + 1

# Auto-suggest next surface based on par and shot number
next_surface = None
next_club = None
if hole_shots:
    last = hole_shots[-1]
    last_dist = last.get("distance_to_hole")
    last_penalty = last.get("penalty", False)

    if shot_number == 2 and par == 3:
        next_surface = "Green"
    elif shot_number == 3 and par == 4:
        next_surface = "Green"
    elif shot_number == 4 and par == 5:
        next_surface = "Green"
    elif last_dist is not None and last_dist <= 130 and not last.get("holed", False):
        next_surface = "Green"

    if last_penalty:
        next_surface = last.get("surface", "Fairway")
        next_club = last.get("club")

if not already_holed:
    st.subheader(f"Shot {shot_number}")

    if shot_number == 1:
        # First shot always from tee
        surface = "Tee"
        st.markdown("**Surface:** Tee (automatic)")
        distance = st.number_input(
            "Distance to hole (meters)", min_value=1, max_value=600,
            value=int(hole_dist) if hole_dist and hole_dist != "?" else 150,
            step=1, key=f"dist_input_{shot_number}",
        )
        club = st.radio("Club", CLUBS, key=f"club_select_{shot_number}", horizontal=True)
        holed = st.checkbox("Holed ✅", key=f"holed_check_{shot_number}")
        penalty = st.checkbox("Penalty shot", value=False, key=f"penalty_check_{shot_number}")
        distance_unit = "meters"

    else:
        # Subsequent shots
        non_tee_surfaces = [s for s in SURFACES if s != "Tee"]
        default_surface = next_surface if next_surface in non_tee_surfaces else non_tee_surfaces[0]
        surface = st.radio(
            "Surface", non_tee_surfaces,
            index=non_tee_surfaces.index(default_surface),
            key=f"surface_select_{shot_number}",
            horizontal=True,
        )

        if surface == "Green":
            distance_unit = "feet"
            distance = st.number_input(
                "Remaining distance to hole (feet)", min_value=1, max_value=200,
                value=None,
                step=1, key=f"dist_input_{shot_number}",
            )
            club = "Putter"
            st.markdown("**Club:** Putter (automatic)")
        else:
            distance_unit = "meters"
            distance = st.number_input(
                "Remaining distance to hole (meters)", min_value=1, max_value=600,
                value=None,
                step=1, key=f"dist_input_{shot_number}",
            )
            suggested_club = next_club or None
            club_index = CLUBS.index(suggested_club) if suggested_club in CLUBS else 0
            club = st.radio("Club", CLUBS, index=club_index, key=f"club_select_{shot_number}", horizontal=True)

        holed = st.checkbox("Holed ✅", key=f"holed_check_{shot_number}")
        penalty = st.checkbox("Penalty shot", value=False, key=f"penalty_check_{shot_number}")

    # ── Add shot button ────────────────────────────────────────────────────────
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
