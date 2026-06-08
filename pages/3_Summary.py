"""
Season summary and historical strokes gained trends.
Mirrors the Summary + Strokes Gained tabs from the original Shiny app.
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import date, timedelta

from db.queries import get_rounds, get_shots_for_round, get_holes, get_round
from utils.strokes_gained import calculate_round_stats, shot_strokes_gained
from utils.constants import COLOR_PRIMARY, COLOR_NEGATIVE, COLOR_POSITIVE

# Use session state values set from app.py
username = st.session_state.get("username", "stefan")
name = st.session_state.get("name", "Stefan")

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
        holes = get_holes(int(r["course_id"]), tee_name=r["tee"])
        stats = calculate_round_stats(shots, holes)
        if stats:
            stats["date"] = r["date"]
            stats["course"] = r["course_name"]
            stats["round_id"] = rid
            stats["tournament"] = r.get("tournament_name") or ""
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
        "tournament": s["tournament"],
        "score": s["score"],
        "par": s["par"],
        "score_vs_par": s["score_vs_par"],
        "fir_pct": s["fir_pct"],
        "gir_pct": s["gir_pct"],
        "gir_birdie_pct": s.get("gir_birdie_pct", 0.0),
        "scrambling": s["scrambling"],
        "putts": s["putts"],
        "three_putts": s["three_putts"],
        "stg_tee": s.get("stg_tee", 0.0),
        "stg_approach": s.get("stg_approach", 0.0),
        "stg_recovery": s.get("stg_recovery", 0.0),
        "stg_short_game": s.get("stg_short_game", 0.0),
        "stg_putting": s.get("stg_putting", 0.0),
        "stg_total": s.get("stg_total", 0.0),
        "stg_approach_fairway": s.get("stg_approach_fairway", 0.0),
        "stg_approach_rough": s.get("stg_approach_rough", 0.0),
        "stg_approach_sand": s.get("stg_approach_sand", 0.0),
        "stg_par3": s.get("stg_par3", 0.0),
        "stg_par4": s.get("stg_par4", 0.0),
        "stg_par5": s.get("stg_par5", 0.0),
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
        # SG by putting distance
        "sg_6ft": s.get("sg_6ft", 0.0),
        "sg_6_10ft": s.get("sg_6_10ft", 0.0),
        "sg_10_30ft": s.get("sg_10_30ft", 0.0),
        "sg_30plus": s.get("sg_30plus", 0.0),
    }
    for s in all_stats
]).sort_values("date")

n = len(df)

# ── Summary metrics ────────────────────────────────────────────────────────────
st.subheader(f"Averages over {n} round{'s' if n > 1 else ''}")

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Avg Score vs Par", f"{df['score_vs_par'].mean():+.1f}")
col2.metric("FIR %", f"{df['fir_pct'].mean()*100:.0f}%")
col3.metric("GIR %", f"{df['gir_pct'].mean()*100:.0f}%")
col4.metric("GIR Birdie %", f"{df['gir_birdie_pct'].mean()*100:.0f}%")
col5.metric("Avg Putts", f"{df['putts'].mean():.1f}")
col6.metric("Scrambling %", f"{df['scrambling'].mean()*100:.0f}%")

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
    "stg_recovery": "Punching Out",
    "stg_short_game": "Short Game",
    "stg_putting": "Putting",
}
colors_stg = [COLOR_PRIMARY, "royalblue", "cyan", "orange", "purple"]

show_rolling = st.checkbox("Show 3-round rolling average", value=False)

fig_stg = go.Figure()
for (col, label), color in zip(stg_cols.items(), colors_stg):
    fig_stg.add_trace(go.Scatter(
        x=df["date"], y=df[col],
        mode="lines+markers", name=label,
        line=dict(color=color, width=2),
        opacity=0.4 if show_rolling else 1.0,
    ))
    if show_rolling and len(df) >= 2:
        rolling = df[col].rolling(window=3, min_periods=1).mean()
        fig_stg.add_trace(go.Scatter(
            x=df["date"], y=rolling,
            mode="lines", name=f"{label} (3-round avg)",
            line=dict(color=color, width=2, dash="dash"),
            showlegend=True,
        ))
fig_stg.add_hline(y=0, line_dash="dash", line_color="gray")
fig_stg.update_layout(
    yaxis_title="Strokes Gained (per 18 holes)",
    height=350, margin=dict(t=30, b=30),
)
st.plotly_chart(fig_stg, use_container_width=True)

# ── Average STG by category ────────────────────────────────────────────────────
col1, col2, col3, col4, col5, col6 = st.columns(6)
for col, (key, label) in zip([col1, col2, col3, col4, col5], stg_cols.items()):
    avg = df[key].mean()
    col.metric(label, f"{avg:+.2f}")

# Total STG
col6.metric("Total STG", f"{df['stg_total'].mean():+.2f}")

# ── Approach by surface ────────────────────────────────────────────────────────
st.subheader("Approach — by Surface (avg per 18 holes)")
ac1, ac2, ac3 = st.columns(3)
for col, label, key in [
    (ac1, "From Fairway", "stg_approach_fairway"),
    (ac2, "From Rough",   "stg_approach_rough"),
    (ac3, "From Sand",    "stg_approach_sand"),
]:
    avg = df[key].mean()
    col.metric(label, f"{avg:+.2f}")

# ── STG by par type ────────────────────────────────────────────────────────────
st.subheader("STG by Hole Type (avg per round)")
pc1, pc2, pc3 = st.columns(3)
for col, label, key in [
    (pc1, "Par 3s", "stg_par3"),
    (pc2, "Par 4s", "stg_par4"),
    (pc3, "Par 5s", "stg_par5"),
]:
    avg = df[key].mean()
    col.metric(label, f"{avg:+.2f}")

st.markdown("---")

# ── Summary table ──────────────────────────────────────────────────────────────
col_title, col_export = st.columns([3, 1])
col_title.subheader("Round-by-Round Summary")

display_df = df[[
    "date", "course", "tournament", "score_vs_par",
    "fir_pct", "gir_pct", "gir_birdie_pct", "scrambling", "putts",
    "stg_tee", "stg_approach", "stg_recovery", "stg_short_game", "stg_putting", "stg_total",
]].copy()

display_df.columns = [
    "Date", "Course", "Tournament", "+/-",
    "FIR %", "GIR %", "GIR Birdie %", "Scrambling", "Putts",
    "STG Tee", "STG App", "STG Punch", "STG SG", "STG Putt", "STG Total",
]
display_df["FIR %"] = (display_df["FIR %"] * 100).round(0).astype(int).astype(str) + "%"
display_df["GIR %"] = (display_df["GIR %"] * 100).round(0).astype(int).astype(str) + "%"
display_df["GIR Birdie %"] = (display_df["GIR Birdie %"] * 100).round(0).astype(int).astype(str) + "%"
display_df["Scrambling"] = (display_df["Scrambling"] * 100).round(0).astype(int).astype(str) + "%"
display_df["+/-"] = display_df["+/-"].apply(lambda x: f"+{x}" if x > 0 else str(x))

sorted_display = display_df.sort_values("Date", ascending=False)
csv_bytes = sorted_display.to_csv(index=False).encode("utf-8")
col_export.download_button("⬇️ Export CSV", csv_bytes, "rounds.csv", "text/csv", use_container_width=True)

st.dataframe(sorted_display, use_container_width=True, hide_index=True)

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
    ("0-6 ft", df["sg_6ft"].mean()),
    ("6-10 ft", df["sg_6_10ft"].mean()),
    ("10-30 ft", df["sg_10_30ft"].mean()),
    ("30+ ft", df["sg_30plus"].mean()),
]

col1, col2, col3, col4, col5 = st.columns(5)
for (label, avg_sg), col in zip(putting_totals, [col1, col2, col3, col4]):
    delta_color = "normal" if avg_sg >= 0 else "inverse"
    col.metric(label, f"{avg_sg:+.2f}", delta=f"{avg_sg:+.2f}", delta_color=delta_color)

total_puts_6ft = int(df["puts_6ft"].sum())
total_makes_6ft = int(df["makes_6ft"].sum())
make_pct_6ft_str = (
    f"{total_makes_6ft / total_puts_6ft * 100:.0f}%"
    if total_puts_6ft > 0 else "—"
)
col5.metric(
    "Make % (≤ 6 ft)",
    make_pct_6ft_str,
    help=f"{total_makes_6ft} made from {total_puts_6ft} attempts across all rounds",
)

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

# ── Per-hole performance ───────────────────────────────────────────────────────
st.markdown("---")
st.subheader("⛳ Hole-by-Hole Performance")
st.caption("Average score vs par and SG per hole across all selected rounds.")

hole_records = []
for s in all_stats:
    for h in s.get("scorecard", []):
        hole_records.append({
            "Hole": h["hole"],
            "score_vs_par": h["score_vs_par"],
            "stg_tee": h["stg_tee"],
            "stg_approach": h["stg_approach"],
            "stg_recovery": h["stg_recovery"],
            "stg_short_game": h["stg_short_game"],
            "stg_putting": h["stg_putting"],
            "par": h["par"],
        })

if hole_records:
    df_holes = pd.DataFrame(hole_records)
    hole_avg = (
        df_holes.groupby("Hole")
        .agg(
            Rounds=("score_vs_par", "count"),
            Par=("par", "first"),
            **{"Avg +/-": ("score_vs_par", "mean")},
            **{"STG Tee": ("stg_tee", "mean")},
            **{"STG Approach": ("stg_approach", "mean")},
            **{"STG Punch": ("stg_recovery", "mean")},
            **{"STG Short": ("stg_short_game", "mean")},
            **{"STG Putt": ("stg_putting", "mean")},
        )
        .reset_index()
    )

    # Color-code avg +/- column
    def colour_svp(val):
        if val < -0.1:
            return "background-color: #076652; color: white"
        if val > 0.5:
            return "background-color: #8b0000; color: white"
        if val > 0.1:
            return "background-color: #c0392b; color: white"
        return ""

    def colour_sg(val):
        if val > 0.1:
            return "background-color: #076652; color: white"
        if val < -0.1:
            return "background-color: #c0392b; color: white"
        return ""

    for col in ["Avg +/-", "STG Tee", "STG Approach", "STG Punch", "STG Short", "STG Putt"]:
        hole_avg[col] = hole_avg[col].round(2)

    styled = (
        hole_avg.style
        .applymap(colour_svp, subset=["Avg +/-"])
        .applymap(colour_sg, subset=["STG Tee", "STG Approach", "STG Punch", "STG Short", "STG Putt"])
        .format({
            "Avg +/-": "{:+.2f}",
            "STG Tee": "{:+.2f}",
            "STG Approach": "{:+.2f}",
            "STG Punch": "{:+.2f}",
            "STG Short": "{:+.2f}",
            "STG Putt": "{:+.2f}",
        })
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)

# ── Shots by Distance ─────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Shots by Distance")
st.caption("All approach shots (non-tee, non-green, non-penalty) from 30 m+.")


@st.cache_data(ttl=300)
def _distance_breakdown(username: str) -> pd.DataFrame:
    rounds = get_rounds(username)
    completed = [r for r in rounds if int(r.get("completed", 0)) == 1]
    records = []

    for r in completed:
        # Build hole par map so we can include par-3 tee shots
        course_id = int(r["course_id"]) if r.get("course_id") else None
        hole_map = {}
        if course_id:
            for h in get_holes(course_id, tee_name=r.get("tee")):
                hole_map[int(h["hole_number"])] = h

        shots = get_shots_for_round(int(r["id"]))
        by_hole: dict[int, list] = {}
        for s in shots:
            by_hole.setdefault(int(s["hole_number"]), []).append(s)

        for hole_num, hole_shots in by_hole.items():
            hole_shots.sort(key=lambda x: int(x["shot_number"]))
            par = int(hole_map.get(hole_num, {}).get("par", 4))

            for i, shot in enumerate(hole_shots):
                if int(shot.get("penalty") or 0):
                    continue
                surface = (shot["surface"] or "").strip()
                if surface == "Green":
                    continue
                # Skip tee shots unless it's a par 3 (where the tee shot = the approach)
                if surface == "Tee" and par != 3:
                    continue
                dist = float(shot["distance_to_hole"]) if shot["distance_to_hole"] else None
                unit = shot["distance_unit"] or "meters"
                if dist is None:
                    continue
                dist_m = dist if unit == "meters" else dist / 3.28084
                if dist_m < 30:
                    continue

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

                # 30–49 m is one bucket; 50m+ follow 25m intervals
                if dist_m < 50:
                    bucket_sort, bucket = 30, "30–49 m"
                else:
                    b = int(dist_m // 25) * 25
                    bucket_sort, bucket = b, f"{b}–{b + 24} m"

                records.append({"bucket_sort": bucket_sort, "bucket": bucket, "sg": sg})

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    agg = (
        df.groupby(["bucket_sort", "bucket"])
        .agg(shots=("sg", "count"), avg_sg=("sg", "mean"), total_sg=("sg", "sum"))
        .reset_index()
        .sort_values("bucket_sort")
        .drop(columns="bucket_sort")
    )
    agg = agg.rename(columns={"bucket": "Distance", "shots": "Shots",
                               "avg_sg": "Avg SG/Shot", "total_sg": "Total SG"})
    agg["Avg SG/Shot"] = agg["Avg SG/Shot"].round(3)
    agg["Total SG"] = agg["Total SG"].round(2)
    return agg


df_dist = _distance_breakdown(username)

if df_dist.empty:
    st.info("No approach shot data found.")
else:
    def _colour_sg_val(val):
        if not isinstance(val, float):
            return ""
        if val > 0.05:
            return f"background-color: {COLOR_POSITIVE}; color: white"
        if val < -0.05:
            return f"background-color: {COLOR_NEGATIVE}; color: white"
        return ""

    styled_dist = (
        df_dist.style
        .applymap(_colour_sg_val, subset=["Avg SG/Shot", "Total SG"])
        .format({"Avg SG/Shot": "{:+.3f}", "Total SG": "{:+.2f}"})
    )
    st.dataframe(styled_dist, use_container_width=True, hide_index=True)

    fig_dist = go.Figure(go.Bar(
        x=df_dist["Distance"],
        y=df_dist["Avg SG/Shot"],
        marker_color=[COLOR_POSITIVE if v >= 0 else COLOR_NEGATIVE for v in df_dist["Avg SG/Shot"]],
        text=[f"{v:+.3f}" for v in df_dist["Avg SG/Shot"]],
        textposition="outside",
        customdata=df_dist["Shots"],
        hovertemplate="%{x}<br>Avg SG: %{y:+.3f}<br>Shots: %{customdata}<extra></extra>",
    ))
    fig_dist.add_hline(y=0, line_color="gray", line_dash="dot")
    fig_dist.update_layout(
        yaxis_title="Avg SG / Shot", xaxis_title="Distance to hole",
        height=300, margin=dict(t=20, b=20),
    )
    st.plotly_chart(fig_dist, use_container_width=True)


# ── Around the Green ──────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Around the Green")
st.caption("Non-green, non-tee shots within 30 m — surface × distance matrix.")

_ATG_SURFS = ["Fairway", "Rough", "Sand", "Recovery"]
_ATG_BUCKS = ["< 10 m", "10–19 m", "20–29 m"]


@st.cache_data(ttl=300)
def _atg_matrix(username: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (avg_sg_pivot, count_pivot) for shots within 30m of the hole."""
    rounds = get_rounds(username)
    completed = [r for r in rounds if int(r.get("completed", 0)) == 1]
    records = []

    for r in completed:
        shots = get_shots_for_round(int(r["id"]))
        by_hole: dict[int, list] = {}
        for s in shots:
            by_hole.setdefault(int(s["hole_number"]), []).append(s)

        for hole_shots in by_hole.values():
            hole_shots.sort(key=lambda x: int(x["shot_number"]))
            for i, shot in enumerate(hole_shots):
                if int(shot.get("penalty") or 0):
                    continue
                surface = (shot["surface"] or "").strip()
                if surface in ("Green", "Tee"):
                    continue
                dist = float(shot["distance_to_hole"]) if shot["distance_to_hole"] else None
                unit = shot["distance_unit"] or "meters"
                if dist is None:
                    continue
                dist_m = dist if unit == "meters" else dist / 3.28084
                if dist_m >= 30:
                    continue

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

                if dist_m < 10:
                    bucket = "< 10 m"
                elif dist_m < 20:
                    bucket = "10–19 m"
                else:
                    bucket = "20–29 m"

                records.append({"surface": surface, "bucket": bucket, "sg": sg})

    if not records:
        return pd.DataFrame(), pd.DataFrame()

    df = pd.DataFrame(records)

    # Build rows for each surface + an "All" total row
    rows_sg, rows_n = [], []
    for surf in _ATG_SURFS + ["All"]:
        sub = df if surf == "All" else df[df["surface"] == surf]
        row_sg: dict = {"Surface": surf}
        row_n: dict = {"Surface": surf}
        for buck in _ATG_BUCKS + ["Total"]:
            cell = sub if buck == "Total" else sub[sub["bucket"] == buck]
            mean_val = cell["sg"].mean()
            row_sg[buck] = round(float(mean_val), 3) if not pd.isna(mean_val) else None
            row_n[buck] = len(cell)
        rows_sg.append(row_sg)
        rows_n.append(row_n)

    df_sg = pd.DataFrame(rows_sg).set_index("Surface")
    df_n = pd.DataFrame(rows_n).set_index("Surface")

    # Drop surface rows with zero shots across all buckets (keep "All" row always)
    df_sg = df_sg.loc[[r for r in df_sg.index if r == "All" or df_n.loc[r, "Total"] > 0]]
    df_n = df_n.loc[[r for r in df_n.index if r == "All" or df_n.loc[r, "Total"] > 0]]

    return df_sg, df_n.astype(int)


df_atg_sg, df_atg_n = _atg_matrix(username)

if df_atg_sg.empty:
    st.info("No short game shot data found.")
else:
    def _colour_atg(val):
        try:
            v = float(val)
        except (TypeError, ValueError):
            return ""
        if pd.isna(v):
            return ""
        if v > 0.05:
            return f"background-color: {COLOR_POSITIVE}; color: white"
        if v < -0.05:
            return f"background-color: {COLOR_NEGATIVE}; color: white"
        return ""

    col_sg, col_n = st.columns(2)
    with col_sg:
        st.markdown("**Avg SG / Shot**")
        styled_atg = (
            df_atg_sg.style
            .applymap(_colour_atg)
            .format("{:+.3f}", na_rep="—")
        )
        st.dataframe(styled_atg, use_container_width=True)
    with col_n:
        st.markdown("**Shots**")
        st.dataframe(df_atg_n, use_container_width=True)
