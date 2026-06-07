"""
Club Stats — performance breakdown by club across all completed rounds.
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from db.queries import get_rounds, get_shots_for_round
from utils.strokes_gained import shot_strokes_gained
from utils.constants import CLUBS, COLOR_POSITIVE, COLOR_NEGATIVE

username = st.session_state.get("username", "stefan")

st.title("🏌️ Club Stats")
st.caption("Aggregated across all completed rounds.")

# ── Load and process shots ─────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def compute_club_stats(username: str) -> pd.DataFrame:
    # Fetch via round→shots to avoid JOIN exclusions from incomplete hole_tees data
    rounds = get_rounds(username)
    completed = [r for r in rounds if int(r.get("completed", 0)) == 1]
    if not completed:
        return pd.DataFrame()

    all_shots = []
    for r in completed:
        for s in get_shots_for_round(int(r["id"])):
            s["_round_id"] = int(r["id"])
            all_shots.append(s)

    if not all_shots:
        return pd.DataFrame()

    # Group by round + hole to compute per-shot SG in sequence
    groups: dict[tuple, list] = {}
    for s in all_shots:
        key = (s["_round_id"], int(s["hole_number"]))
        groups.setdefault(key, []).append(s)

    records = []
    for hole_shots in groups.values():
        hole_shots.sort(key=lambda x: int(x["shot_number"]))
        for i, shot in enumerate(hole_shots):
            club = shot.get("club")
            # penalty stored as "0"/"1" string or 0/1 int from Turso
            if not club or int(shot.get("penalty") or 0):
                continue
            surface = (shot["surface"] or "").strip()
            dist = float(shot["distance_to_hole"]) if shot["distance_to_hole"] else 0
            unit = shot["distance_unit"] or "meters"
            holed = bool(int(shot["holed"] or 0))

            if i + 1 < len(hole_shots):
                ns = hole_shots[i + 1]
                sg = shot_strokes_gained(
                    surface, dist, unit,
                    (ns["surface"] or "").strip(),
                    float(ns["distance_to_hole"]) if ns["distance_to_hole"] else 0,
                    ns["distance_unit"] or "meters",
                    False,
                )
            else:
                sg = shot_strokes_gained(surface, dist, unit, None, None, None, True)

            dist_m = dist if unit == "meters" else dist / 3.28084
            records.append({
                "club": club,
                "_n": 1,          # always 1 — for counting all shots including those with sg=None
                "surface": surface,
                "dist_to_hole_m": dist_m,
                "sg": sg,
            })

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    agg = (
        df.groupby("club")
        .agg(
            shots=("_n", "sum"),                                        # all shots, not just those with SG
            avg_sg=("sg", "mean"),                                      # NaN excluded by mean — correct
            avg_dist_m=("dist_to_hole_m", "mean"),
            top_surface=("surface", lambda x: x.value_counts().index[0]),
        )
        .reset_index()
    )
    club_order = {c: i for i, c in enumerate(CLUBS)}
    agg["_order"] = agg["club"].map(club_order).fillna(99)
    agg = agg.sort_values("_order").drop(columns="_order")
    agg["avg_sg"] = agg["avg_sg"].round(3)
    agg["avg_dist_m"] = agg["avg_dist_m"].round(0).astype(int)
    return agg


df_clubs = compute_club_stats(username)

if df_clubs.empty:
    st.info("No shot data yet. Complete some rounds first.")
    st.stop()

# ── Summary table ──────────────────────────────────────────────────────────────
st.subheader("Performance by Club")

display = df_clubs.rename(columns={
    "club": "Club",
    "shots": "Shots",
    "avg_sg": "Avg SG / Shot",
    "avg_dist_m": "Avg Dist to Hole (m)",
    "top_surface": "Most Common Surface",
})

def colour_sg(val):
    if val > 0.05:
        return "background-color: #076652; color: white"
    if val < -0.05:
        return "background-color: #c0392b; color: white"
    return ""

styled = (
    display.style
    .applymap(colour_sg, subset=["Avg SG / Shot"])
    .format({"Avg SG / Shot": "{:+.3f}"})
)
st.dataframe(styled, use_container_width=True, hide_index=True)

# ── SG per club bar chart ──────────────────────────────────────────────────────
st.subheader("Strokes Gained per Shot by Club")

clubs_with_sg = df_clubs.dropna(subset=["avg_sg"])
if not clubs_with_sg.empty:
    fig = go.Figure(go.Bar(
        x=clubs_with_sg["club"],
        y=clubs_with_sg["avg_sg"],
        marker_color=[COLOR_POSITIVE if v >= 0 else COLOR_NEGATIVE for v in clubs_with_sg["avg_sg"]],
        text=[f"{v:+.3f}" for v in clubs_with_sg["avg_sg"]],
        textposition="outside",
    ))
    fig.add_hline(y=0, line_color="gray")
    fig.update_layout(
        yaxis_title="Avg SG per shot",
        xaxis_title="Club",
        height=350,
        margin=dict(t=30, b=30),
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Shot count by club ─────────────────────────────────────────────────────────
st.subheader("Shot Frequency by Club")

fig2 = go.Figure(go.Bar(
    x=df_clubs["club"],
    y=df_clubs["shots"],
    marker_color="steelblue",
    text=df_clubs["shots"],
    textposition="outside",
))
fig2.update_layout(
    yaxis_title="Total shots",
    xaxis_title="Club",
    height=300,
    margin=dict(t=20, b=30),
)
st.plotly_chart(fig2, use_container_width=True)

if st.button("🔄 Refresh data"):
    st.cache_data.clear()
    st.rerun()
