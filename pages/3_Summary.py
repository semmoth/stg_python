"""
Season summary and historical strokes gained trends.
Mirrors the Summary + Strokes Gained tabs from the original Shiny app.
"""
import streamlit as st
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import date, timedelta

from db.queries import get_rounds, get_shots_for_round, get_holes, get_round
from utils.strokes_gained import calculate_round_stats
from utils.constants import COLOR_PRIMARY, COLOR_NEGATIVE, COLOR_POSITIVE, TEES_ID

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

# ── Page ───────────────────────────────────────────────────────────────────────
st.title("📈 Season Summary")

rounds = get_rounds(username)
completed_rounds = [r for r in rounds if int(r.get("completed", 0)) == 1]

if not completed_rounds:
    st.info("No completed rounds yet.")
    st.stop()

# ── Date filter ────────────────────────────────────────────────────────────────
all_dates = sorted([r["date"] for r in completed_rounds])
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("From", value=date.fromisoformat(all_dates[0]))
with col2:
    end_date = st.date_input("To", value=date.today())

filtered_rounds = [
    r for r in completed_rounds
    if start_date <= date.fromisoformat(r["date"]) <= end_date
]

if not filtered_rounds:
    st.warning("No rounds in selected date range.")
    st.stop()

# ── Compute stats for all filtered rounds ─────────────────────────────────────
@st.cache_data(ttl=300)
def load_all_stats(round_ids: tuple, username: str):
    all_stats = []
    for rid in round_ids:
        r = get_round(rid)
        shots = get_shots_for_round(rid)
        holes = get_holes(int(r["course_id"]), TEES_ID[r["tee"]])
        stats = calculate_round_stats(shots, holes)
        if stats:
            stats["date"] = r["date"]
            stats["course"] = r["course_name"]
            stats["round_id"] = rid
            all_stats.append(stats)
    return all_stats

round_ids = tuple(int(r["id"]) for r in filtered_rounds)
all_stats = load_all_stats(round_ids, username)

if not all_stats:
    st.warning("Could not calculate stats for selected rounds.")
    st.stop()

df = pd.DataFrame([
    {
        "date": s["date"],
        "course": s["course"],
        "score": s["score"],
        "par": s["par"],
        "score_vs_par": s["score_vs_par"],
        "fir_pct": s["fir_pct"],
        "gir_pct": s["gir_pct"],
        "scrambling": s["scrambling"],
        "putts": s["putts"],
        "three_putts": s["three_putts"],
        "stg_tee": s["stg_tee"],
        "stg_approach": s["stg_approach"],
        "stg_short_game": s["stg_short_game"],
        "stg_putting": s["stg_putting"],
        "stg_total": s["stg_total"],
        "avg_drive": s.get("avg_drive"),
        "tiger5_par5_bogeys": s.get("tiger5_par5_bogeys", 0),
        "tiger5_double_bogeys": s.get("tiger5_double_bogeys", 0),
        "tiger5_three_putts": s.get("tiger5_three_putts", 0),
        "tiger5_scoring_bogeys": s.get("tiger5_scoring_bogeys", 0),
        "tiger5_up_and_downs": s.get("tiger5_up_and_downs", 0),
        # Putting by distance
        "puts_6ft": s.get("puts_6ft", 0),
        "makes_6ft": s.get("makes_6ft", 0),
        "puts_6_10ft": s.get("puts_6_10ft", 0),
        "makes_6_10ft": s.get("makes_6_10ft", 0),
        "puts_10_30ft": s.get("puts_10_30ft", 0),
        "makes_10_30ft": s.get("makes_10_30ft", 0),
        "puts_30plus": s.get("puts_30plus", 0),
        "makes_30plus": s.get("makes_30plus", 0),
    }
    for s in all_stats
]).sort_values("date")

n = len(df)

# ── Summary metrics ────────────────────────────────────────────────────────────
st.subheader(f"Averages over {n} round{'s' if n > 1 else ''}")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Avg Score vs Par", f"{df['score_vs_par'].mean():+.1f}")
col2.metric("FIR %", f"{df['fir_pct'].mean()*100:.0f}%")
col3.metric("GIR %", f"{df['gir_pct'].mean()*100:.0f}%")
col4.metric("Avg Putts", f"{df['putts'].mean():.1f}")
col5.metric("Scrambling %", f"{df['scrambling'].mean()*100:.0f}%")

st.markdown("---")

# ── Score trend ────────────────────────────────────────────────────────────────
st.subheader("Score vs Par — Trend")

fig_score = go.Figure()
fig_score.add_trace(go.Scatter(
    x=df["date"], y=df["score_vs_par"],
    mode="lines+markers",
    line=dict(color=COLOR_PRIMARY, width=2),
    marker=dict(
        color=[COLOR_NEGATIVE if v > 0 else COLOR_POSITIVE for v in df["score_vs_par"]],
        size=8,
    ),
    name="Score vs Par",
))
fig_score.add_hline(y=0, line_dash="dash", line_color="gray")
fig_score.update_layout(
    yaxis_title="Score vs Par", xaxis_title="Date",
    height=300, margin=dict(t=30, b=30),
)
st.plotly_chart(fig_score, use_container_width=True)

st.markdown("---")

# ── Strokes Gained trends ──────────────────────────────────────────────────────
st.subheader("Strokes Gained — Trends")

stg_cols = {
    "stg_tee": "Tee",
    "stg_approach": "Approach",
    "stg_short_game": "Short Game",
    "stg_putting": "Putting",
}
colors_stg = [COLOR_PRIMARY, "royalblue", "orange", "purple"]

fig_stg = go.Figure()
for (col, label), color in zip(stg_cols.items(), colors_stg):
    fig_stg.add_trace(go.Scatter(
        x=df["date"], y=df[col],
        mode="lines+markers", name=label,
        line=dict(color=color, width=2),
    ))
fig_stg.add_hline(y=0, line_dash="dash", line_color="gray")
fig_stg.update_layout(
    yaxis_title="Strokes Gained (per 18 holes)",
    height=350, margin=dict(t=30, b=30),
)
st.plotly_chart(fig_stg, use_container_width=True)

# ── Average STG by category ────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
for col, (key, label) in zip([col1, col2, col3, col4], stg_cols.items()):
    avg = df[key].mean()
    col.metric(label, f"{avg:+.2f}")

st.markdown("---")

# ── Summary table ──────────────────────────────────────────────────────────────
st.subheader("Round-by-Round Summary")

display_df = df[[
    "date", "course", "score_vs_par",
    "fir_pct", "gir_pct", "scrambling", "putts",
    "stg_tee", "stg_approach", "stg_short_game", "stg_putting", "stg_total",
]].copy()

display_df.columns = [
    "Date", "Course", "+/-",
    "FIR %", "GIR %", "Scrambling", "Putts",
    "STG Tee", "STG App", "STG SG", "STG Putt", "STG Total",
]
display_df["FIR %"] = (display_df["FIR %"] * 100).round(0).astype(int).astype(str) + "%"
display_df["GIR %"] = (display_df["GIR %"] * 100).round(0).astype(int).astype(str) + "%"
display_df["Scrambling"] = (display_df["Scrambling"] * 100).round(0).astype(int).astype(str) + "%"
display_df["+/-"] = display_df["+/-"].apply(lambda x: f"+{x}" if x > 0 else str(x))

st.dataframe(display_df.sort_values("Date", ascending=False), use_container_width=True, hide_index=True)

# ── Driving stats ──────────────────────────────────────────────────────────────
drive_df = df[df["avg_drive"].notna()]
if not drive_df.empty:
    st.markdown("---")
    st.subheader("Driving Distance")
    fig_drive = go.Figure(go.Bar(
        x=drive_df["date"], y=drive_df["avg_drive"],
        marker_color=COLOR_PRIMARY,
        text=drive_df["avg_drive"].round(0).astype(int).astype(str) + " m",
        textposition="outside",
    ))
    fig_drive.update_layout(
        yaxis_title="Avg Drive (m)", height=280, margin=dict(t=30, b=30),
    )
    st.plotly_chart(fig_drive, use_container_width=True)

# ── Putting by Distance — Season Summary ──────────────────────────────────────
st.markdown("---")
st.subheader("Putting by Distance — Season Summary")

putting_totals = [
    ("0-6 ft", df["makes_6ft"].sum(), df["puts_6ft"].sum()),
    ("6-10 ft", df["makes_6_10ft"].sum(), df["puts_6_10ft"].sum()),
    ("10-30 ft", df["makes_10_30ft"].sum(), df["puts_10_30ft"].sum()),
    ("30+ ft", df["makes_30plus"].sum(), df["puts_30plus"].sum()),
]

col1, col2, col3, col4 = st.columns(4)
for (label, makes, attempts), col in zip(putting_totals, [col1, col2, col3, col4]):
    if attempts > 0:
        pct = (makes / attempts) * 100
        col.metric(label, f"{makes}/{attempts}", delta=f"{pct:.0f}%")
    else:
        col.metric(label, "0/0", delta="N/A")

st.markdown("---")
st.subheader("🐯 Tiger 5 Rules — Season Summary")

col1, col2, col3 = st.columns(3)
with col1:
    val = df["tiger5_par5_bogeys"].sum()
    st.metric("Par 5 Bogeys", val, delta="✗" if val > 0 else "✓", delta_color="inverse" if val > 0 else "normal")
with col2:
    val = df["tiger5_double_bogeys"].sum()
    st.metric("Double Bogeys", val, delta="✗" if val > 0 else "✓", delta_color="inverse" if val > 0 else "normal")
with col3:
    val = df["tiger5_three_putts"].sum()
    st.metric("3-Putts", val, delta="✗" if val > 0 else "✓", delta_color="inverse" if val > 0 else "normal")

col4, col5 = st.columns(2)
with col4:
    val = df["tiger5_scoring_bogeys"].sum()
    st.metric("Scoring Club Bogeys", val, delta="✗" if val > 0 else "✓", delta_color="inverse" if val > 0 else "normal")
with col5:
    val = df["tiger5_up_and_downs"].sum()
    st.metric("Missed Easy Up & Downs", val, delta="✗" if val > 0 else "✓", delta_color="inverse" if val > 0 else "normal")
