"""
Last Round stats page — mirrors the 'Last Round' tab from the original Shiny app.
Shows: scorecard, score vs par chart, round stats, STG breakdown, score distribution.
"""
import streamlit as st
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from db.queries import get_rounds, get_shots_for_round, get_holes, get_round
from utils.strokes_gained import calculate_round_stats
from utils.constants import COLOR_PRIMARY, COLOR_ACCENT, COLOR_NEGATIVE, COLOR_POSITIVE

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
st.title("📊 Last Round")

rounds = get_rounds(username)
completed_rounds = [r for r in rounds if int(r.get("completed", 0)) == 1]

if not completed_rounds:
    st.info("No completed rounds found. Enter a round first.")
    st.stop()

# ── Round selector ─────────────────────────────────────────────────────────────
round_options = {
    f"{r['date']} — {r['course_name']} ({r['tee']})": r["id"]
    for r in completed_rounds
}
selected_label = st.selectbox("Select round", list(round_options.keys()))
selected_round_id = int(round_options[selected_label])

round_info = get_round(selected_round_id)
shots = get_shots_for_round(selected_round_id)
holes = get_holes(int(round_info["course_id"]))

if not shots:
    st.warning("No shots found for this round.")
    st.stop()

stats = calculate_round_stats(shots, holes)
scorecard = stats.get("scorecard", [])

# ── Score header ───────────────────────────────────────────────────────────────
svp = stats["score_vs_par"]
svp_str = f"+{svp}" if svp > 0 else str(svp)
score_color = COLOR_NEGATIVE if svp > 0 else COLOR_POSITIVE

st.markdown(
    f"<h2 style='color:{score_color};'>{stats['score']} ({svp_str})</h2>",
    unsafe_allow_html=True,
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("FIR", f"{stats['fir_pct']*100:.0f}%")
col2.metric("GIR", f"{stats['gir_pct']*100:.0f}%")
col3.metric("Putts", stats["putts"])
col4.metric("3-Putts", stats["three_putts"])

st.markdown("---")

# ── Score vs Par chart ─────────────────────────────────────────────────────────
if scorecard:
    cumulative = []
    running = 0
    for h in scorecard:
        running += h["score_vs_par"]
        cumulative.append(running)

    fig_score = go.Figure()
    fig_score.add_trace(go.Scatter(
        x=[h["hole"] for h in scorecard],
        y=cumulative,
        mode="lines+markers",
        line=dict(color=COLOR_PRIMARY, width=2),
        marker=dict(
            color=[COLOR_NEGATIVE if v > 0 else COLOR_POSITIVE for v in cumulative],
            size=8,
        ),
        name="Score vs Par",
    ))
    fig_score.add_hline(y=0, line_dash="dash", line_color="gray")
    fig_score.update_layout(
        title="Cumulative Score vs Par",
        xaxis_title="Hole",
        yaxis_title="Score vs Par",
        xaxis=dict(tickmode="linear", tick0=1, dtick=1),
        height=300,
        margin=dict(t=40, b=30),
    )
    st.plotly_chart(fig_score, use_container_width=True)

# ── Scorecard table ────────────────────────────────────────────────────────────
st.subheader("Scorecard")

def score_color_style(score_vs_par: int) -> str:
    if score_vs_par <= -2:
        return "background-color: gold; color: black;"
    if score_vs_par == -1:
        return "background-color: #076652; color: white;"
    if score_vs_par == 0:
        return ""
    if score_vs_par == 1:
        return "background-color: #ffcccc;"
    return "background-color: firebrick; color: white;"

df_card = pd.DataFrame([
    {
        "Hole": h["hole"],
        "Par": h["par"],
        "Score": h["score"],
        "+/-": f"+{h['score_vs_par']}" if h["score_vs_par"] > 0 else str(h["score_vs_par"]),
        "Putts": h["putts"],
        "GIR": "✓" if h["gir"] else "✗",
        "FIR": "✓" if h.get("fir") else ("—" if h.get("fir") is None else "✗"),
    }
    for h in scorecard
])
st.dataframe(df_card, use_container_width=True, hide_index=True)

st.markdown("---")

# ── Strokes Gained breakdown ───────────────────────────────────────────────────
st.subheader("Strokes Gained (normalised to 18 holes)")

stg_values = {
    "Tee": stats["stg_tee"],
    "Approach": stats["stg_approach"],
    "Short Game": stats["stg_short_game"],
    "Putting": stats["stg_putting"],
}

col1, col2, col3, col4 = st.columns(4)
for col, (label, val) in zip([col1, col2, col3, col4], stg_values.items()):
    delta_color = "normal" if val >= 0 else "inverse"
    col.metric(label, f"{val:+.2f}", delta=f"{val:+.2f}", delta_color=delta_color)

fig_stg = go.Figure(go.Bar(
    x=list(stg_values.keys()),
    y=list(stg_values.values()),
    marker_color=[COLOR_POSITIVE if v >= 0 else COLOR_NEGATIVE for v in stg_values.values()],
    text=[f"{v:+.2f}" for v in stg_values.values()],
    textposition="outside",
))
fig_stg.add_hline(y=0, line_color="gray")
fig_stg.update_layout(
    title="Strokes Gained by Category",
    yaxis_title="Strokes Gained",
    height=320,
    margin=dict(t=40, b=30),
)
st.plotly_chart(fig_stg, use_container_width=True)

# ── Score distribution pie chart ───────────────────────────────────────────────
st.subheader("Score Distribution")

dist = stats["score_distribution"]
labels = [k for k, v in dist.items() if v > 0]
values = [v for v in dist.values() if v > 0]
colors = ["gold", "#076652", "#cce5cc", "#ffcccc", "firebrick", "#8b0000"]

if labels:
    fig_pie = px.pie(
        names=labels, values=values,
        color=labels,
        color_discrete_map=dict(zip(
            ["Eagle", "Birdie", "Par", "Bogey", "Double", "Worse"],
            colors,
        )),
        hole=0.3,
    )
    fig_pie.update_layout(height=320, margin=dict(t=20, b=20))
    st.plotly_chart(fig_pie, use_container_width=True)

# ── Driving stats (if available) ──────────────────────────────────────────────
if stats.get("avg_drive"):
    st.markdown("---")
    st.subheader("Driving")
    col1, col2 = st.columns(2)
    col1.metric("Avg Drive", f"{stats['avg_drive']} m")
    if stats["driving_distances"]:
        col2.metric("Longest Drive", f"{max(stats['driving_distances']):.0f} m")
