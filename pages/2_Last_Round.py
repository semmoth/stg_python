"""
Last Round stats page.
Shows: scorecard, score vs par chart, round stats, STG breakdown, score distribution.
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from db.queries import get_rounds, get_shots_for_round, get_holes, get_round
from utils.strokes_gained import calculate_round_stats
from utils.constants import COLOR_PRIMARY, COLOR_ACCENT, COLOR_NEGATIVE, COLOR_POSITIVE

username = st.session_state.get("username", "stefan")
name = st.session_state.get("name", "Stefan")

# ── Page ───────────────────────────────────────────────────────────────────────
st.title("📊 Last Round")

rounds = get_rounds(username)
completed_rounds = [r for r in rounds if int(r.get("completed", 0)) == 1]

if not completed_rounds:
    st.info("No completed rounds found. Enter a round first.")
    st.stop()

# ── Round selector ─────────────────────────────────────────────────────────────
round_options = {}
for r in completed_rounds:
    label = f"{r['date']} — {r['course_name']} ({r['tee']})"
    if r.get("tournament_name"):
        label += f" — {r['tournament_name']}"
    round_options[label] = r["id"]
selected_label = st.selectbox("Select round", list(round_options.keys()))
selected_round_id = int(round_options[selected_label])

round_info = get_round(selected_round_id)
shots = get_shots_for_round(selected_round_id)
holes = get_holes(int(round_info["course_id"]), tee_name=round_info["tee"])

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

col5, col6, col7, col8, col9 = st.columns(5)
col5.metric("Scrambling", f"{stats['scrambling']*100:.0f}%")
col6.metric("GIR Birdie %", f"{stats.get('gir_birdie_pct', 0)*100:.0f}%")
par3_vs = stats["par3_vs_par"]
col7.metric("Par 3 vs Par", f"{par3_vs:+d}")
par4_vs = stats["par4_vs_par"]
col8.metric("Par 4 vs Par", f"{par4_vs:+d}")
par5_vs = stats["par5_vs_par"]
col9.metric("Par 5 vs Par", f"{par5_vs:+d}")

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

# ── Scorecard ─────────────────────────────────────────────────────────────────
st.subheader("Scorecard")

def score_color_style(score_vs_par: int) -> str:
    if score_vs_par <= -2:
        return "background-color: #ff8c00; color: white;"
    if score_vs_par == -1:
        return "background-color: #e74c3c; color: white;"
    if score_vs_par == 0:
        return "background-color: #f8f9fa; color: #212529;"
    if score_vs_par == 1:
        return "background-color: #add8e6; color: black;"
    return "background-color: #00008b; color: white;"

scorecards_html = []
for h in scorecard:
    score_vs_par = h["score_vs_par"]
    score_vs_par_str = f"+{score_vs_par}" if score_vs_par > 0 else str(score_vs_par)
    gir = "✓" if h["gir"] else "✗"
    fir_value = h.get("fir")
    fir_icon = "—" if fir_value is None else ("✓" if fir_value else "✗")
    fir_color = "#6c757d" if fir_value is None else ("#28a745" if fir_value else "#e74c3c")
    score_style = score_color_style(score_vs_par)
    card_html = f"""
    <div style="display:flex; flex-direction:column; gap:6px; min-width:210px; width:210px; padding:12px; border:1px solid #ddd; border-radius:10px; background:#ffffff; box-shadow:0 1px 4px rgba(0,0,0,0.04);">
      <div style="font-weight:700; font-size:1rem; color:#0d6efd;">Hole {h['hole']}</div>
      <div style="display:grid; grid-template-columns: repeat(2, minmax(90px, 1fr)); gap:8px;">
        <div style="text-align:center; padding:8px 6px; border-radius:8px; background:#f8f9fa;"><div style="font-size:0.72rem; color:#6c757d;">Par</div><div style="font-weight:700;">{h['par']}</div></div>
        <div style="text-align:center; padding:8px 6px; border-radius:8px; {score_style}"><div style="font-size:0.72rem; color:#6c757d;">Score</div><div style="font-weight:700;">{h['score']}</div></div>
        <div style="text-align:center; padding:8px 6px; border-radius:8px; background:#f8f9fa;"><div style="font-size:0.72rem; color:#6c757d;">vs Par</div><div style="font-weight:700;">{score_vs_par_str}</div></div>
        <div style="text-align:center; padding:8px 6px; border-radius:8px; background:#f8f9fa;"><div style="font-size:0.72rem; color:#6c757d;">Putts</div><div style="font-weight:700;">{h['putts']}</div></div>
        <div style="text-align:center; padding:8px 6px; border-radius:8px; background:#f8f9fa;"><div style="font-size:0.72rem; color:#6c757d;">GIR</div><div style="font-weight:700; color:#28a745;">{gir}</div></div>
        <div style="text-align:center; padding:8px 6px; border-radius:8px; background:#f8f9fa;"><div style="font-size:0.72rem; color:#6c757d;">FIR</div><div style="font-weight:700; color:{fir_color};">{fir_icon}</div></div>
      </div>
    </div>
    """
    scorecards_html.append(card_html)

st.markdown(
    "<div style='display:flex; flex-wrap:wrap; gap:12px; padding-bottom:8px; overflow-x:auto; white-space:nowrap;'>"
    + "".join(scorecards_html)
    + "</div>",
    unsafe_allow_html=True,
)

st.markdown("---")

# ── Strokes Gained breakdown ───────────────────────────────────────────────────
st.subheader("Strokes Gained (normalised to 18 holes)")

stg_values = {
    "Tee": stats.get("stg_tee", 0.0),
    "Approach": stats.get("stg_approach", 0.0),
    "Punching Out": stats.get("stg_recovery", 0.0),
    "Short Game": stats.get("stg_short_game", 0.0),
    "Putting": stats.get("stg_putting", 0.0),
    "Total": stats.get("stg_total", 0.0),
}

col1, col2, col3, col4, col5, col6 = st.columns(6)
for col, (label, val) in zip([col1, col2, col3, col4, col5, col6], stg_values.items()):
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

# ── Approach breakdown by surface ──────────────────────────────────────────────
st.subheader("Approach — by Surface (normalised to 18 holes)")
a_col1, a_col2, a_col3 = st.columns(3)
for col, label, key in [
    (a_col1, "From Fairway", "stg_approach_fairway"),
    (a_col2, "From Rough",   "stg_approach_rough"),
    (a_col3, "From Sand",    "stg_approach_sand"),
]:
    val = stats.get(key, 0.0)
    col.metric(label, f"{val:+.2f}", delta=f"{val:+.2f}", delta_color="normal" if val >= 0 else "inverse")

# ── STG by par type ────────────────────────────────────────────────────────────
st.subheader("STG by Hole Type (round total)")
p_col1, p_col2, p_col3 = st.columns(3)
for col, label, key in [
    (p_col1, "Par 3s", "stg_par3"),
    (p_col2, "Par 4s", "stg_par4"),
    (p_col3, "Par 5s", "stg_par5"),
]:
    val = stats.get(key, 0.0)
    col.metric(label, f"{val:+.2f}", delta=f"{val:+.2f}", delta_color="normal" if val >= 0 else "inverse")

st.markdown("---")

# ── Score distribution ────────────────────────────────────────────────────────
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

# ── Putting by Distance ───────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Putting by Distance")

putting_data = [
    ("0-6 ft",   stats.get("sg_6ft",    0.0)),
    ("6-10 ft",  stats.get("sg_6_10ft", 0.0)),
    ("10-30 ft", stats.get("sg_10_30ft",0.0)),
    ("30+ ft",   stats.get("sg_30plus", 0.0)),
]

col1, col2, col3, col4 = st.columns(4)
for (label, sg_value), col in zip(putting_data, [col1, col2, col3, col4]):
    col.metric(label, f"{sg_value:+.2f}", delta=f"{sg_value:+.2f}",
               delta_color="normal" if sg_value >= 0 else "inverse")

# ── Tiger 5 Rules ─────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("🐯 Tiger 5 Rules Scorecard")

col1, col2, col3 = st.columns(3)
with col1:
    val = stats["tiger5_par5_bogeys"]
    st.metric("Par 5 Bogeys", val, delta="✗" if val > 0 else "✓", delta_color="inverse" if val > 0 else "normal")
with col2:
    val = stats["tiger5_double_bogeys"]
    st.metric("Double Bogeys", val, delta="✗" if val > 0 else "✓", delta_color="inverse" if val > 0 else "normal")
with col3:
    val = stats["tiger5_three_putts"]
    st.metric("3-Putts", val, delta="✗" if val > 0 else "✓", delta_color="inverse" if val > 0 else "normal")

col4, col5 = st.columns(2)
with col4:
    val = stats["tiger5_scoring_bogeys"]
    st.metric("Scoring Club Bogeys", val, delta="✗" if val > 0 else "✓", delta_color="inverse" if val > 0 else "normal")
with col5:
    val = stats["tiger5_up_and_downs"]
    st.metric("Missed Easy Up & Downs", val, delta="✗" if val > 0 else "✓", delta_color="inverse" if val > 0 else "normal")

# ── Round Comparison ──────────────────────────────────────────────────────────
st.markdown("---")
with st.expander("🔁 Compare with another round"):
    other_options = {k: v for k, v in round_options.items() if v != selected_round_id}
    if not other_options:
        st.info("Only one completed round available — nothing to compare.")
    else:
        cmp_label = st.selectbox("Compare with", list(other_options.keys()), key="cmp_round")
        cmp_id = int(other_options[cmp_label])
        cmp_info = get_round(cmp_id)
        cmp_shots = get_shots_for_round(cmp_id)
        cmp_holes = get_holes(int(cmp_info["course_id"]), tee_name=cmp_info["tee"])
        cmp_stats = calculate_round_stats(cmp_shots, cmp_holes)

        if cmp_stats:
            st.markdown(f"**{selected_label}** vs **{cmp_label}**")

            metrics = [
                ("Score vs Par",   f"{stats['score_vs_par']:+d}",                        f"{cmp_stats['score_vs_par']:+d}"),
                ("FIR",            f"{stats['fir_pct']*100:.0f}%",                        f"{cmp_stats['fir_pct']*100:.0f}%"),
                ("GIR",            f"{stats['gir_pct']*100:.0f}%",                        f"{cmp_stats['gir_pct']*100:.0f}%"),
                ("GIR Birdie %",   f"{stats.get('gir_birdie_pct',0)*100:.0f}%",           f"{cmp_stats.get('gir_birdie_pct',0)*100:.0f}%"),
                ("Putts",          str(stats["putts"]),                                    str(cmp_stats["putts"])),
                ("Scrambling",     f"{stats['scrambling']*100:.0f}%",                     f"{cmp_stats['scrambling']*100:.0f}%"),
            ]
            hdr, c1, c2 = st.columns([2, 1, 1])
            hdr.markdown("**Metric**")
            c1.markdown(f"**{stats['score']} ({stats['score_vs_par']:+d})**")
            c2.markdown(f"**{cmp_stats['score']} ({cmp_stats['score_vs_par']:+d})**")
            for label, v1, v2 in metrics:
                h, a, b = st.columns([2, 1, 1])
                h.write(label)
                a.write(v1)
                b.write(v2)

            sg_cats = ["Tee", "Approach", "Punching Out", "Short Game", "Putting"]
            sg_keys = ["stg_tee", "stg_approach", "stg_recovery", "stg_short_game", "stg_putting"]
            fig_cmp = go.Figure()
            fig_cmp.add_trace(go.Bar(
                name=selected_label[:30],
                x=sg_cats,
                y=[stats.get(k, 0) for k in sg_keys],
                marker_color=COLOR_PRIMARY,
                text=[f"{stats.get(k,0):+.2f}" for k in sg_keys],
                textposition="outside",
            ))
            fig_cmp.add_trace(go.Bar(
                name=cmp_label[:30],
                x=sg_cats,
                y=[cmp_stats.get(k, 0) for k in sg_keys],
                marker_color=COLOR_ACCENT,
                text=[f"{cmp_stats.get(k,0):+.2f}" for k in sg_keys],
                textposition="outside",
            ))
            fig_cmp.add_hline(y=0, line_color="gray")
            fig_cmp.update_layout(
                barmode="group",
                title="Strokes Gained Comparison",
                yaxis_title="Strokes Gained",
                height=350,
                margin=dict(t=40, b=30),
            )
            st.plotly_chart(fig_cmp, use_container_width=True)
