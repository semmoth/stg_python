"""
Practice Log — record and review practice sessions.
"""
import streamlit as st
import plotly.express as px
import pandas as pd
from datetime import date

from db.queries import create_practice_session, get_practice_sessions, delete_practice_session

username = st.session_state.get("username", "stefan")

st.title("📋 Practice Log")

PRACTICE_TYPES = [
    "Driving Range",
    "Putting",
    "Chipping / Short Game",
    "Bunker Play",
    "Course (non-scored)",
    "Video Review",
    "Fitness",
    "Mental Game",
]

# ── Log a new session ──────────────────────────────────────────────────────────
st.subheader("Log a Practice Session")

with st.form("practice_form"):
    col1, col2 = st.columns(2)
    with col1:
        session_date = st.date_input("Date", value=date.today())
        session_type = st.selectbox("Type", PRACTICE_TYPES)
    with col2:
        duration = st.number_input("Duration (minutes)", min_value=5, max_value=480, value=60, step=5)
        rating = st.slider("Quality rating", min_value=1, max_value=5, value=3,
                           help="1 = poor, 5 = excellent")
    notes = st.text_area("Notes / focus area (optional)", placeholder="e.g. worked on lag putting from 20+ ft")
    submitted = st.form_submit_button("Log Session", type="primary", use_container_width=True)

    if submitted:
        create_practice_session(
            username=username,
            date=str(session_date),
            type=session_type,
            duration_minutes=duration,
            notes=notes.strip() or None,
            rating=rating,
        )
        st.success(f"Logged {duration} min of {session_type}.")
        st.rerun()

st.markdown("---")

# ── Load sessions ──────────────────────────────────────────────────────────────
sessions = get_practice_sessions(username)

if not sessions:
    st.info("No practice sessions logged yet.")
    st.stop()

df = pd.DataFrame(sessions)
df["date"] = pd.to_datetime(df["date"])
df["duration_minutes"] = df["duration_minutes"].fillna(0).astype(int)

# ── Summary metrics ────────────────────────────────────────────────────────────
st.subheader(f"Summary — {len(df)} sessions")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total sessions", len(df))
col2.metric("Total hours", f"{df['duration_minutes'].sum() / 60:.1f}")
col3.metric("Avg session (min)", f"{df['duration_minutes'].mean():.0f}")
col4.metric("Avg quality", f"{df['rating'].mean():.1f} / 5")

# ── Time by type ──────────────────────────────────────────────────────────────
by_type = df.groupby("type")["duration_minutes"].sum().reset_index().sort_values("duration_minutes", ascending=False)
by_type["hours"] = (by_type["duration_minutes"] / 60).round(1)

fig_pie = px.pie(
    by_type, names="type", values="duration_minutes",
    hole=0.3, title="Time split by practice type",
)
fig_pie.update_layout(height=320, margin=dict(t=40, b=20))
st.plotly_chart(fig_pie, use_container_width=True)

# ── Duration trend ────────────────────────────────────────────────────────────
fig_trend = px.bar(
    df.sort_values("date"),
    x="date", y="duration_minutes",
    color="type",
    title="Practice sessions over time",
    labels={"duration_minutes": "Minutes", "date": "Date", "type": "Type"},
)
fig_trend.update_layout(height=300, margin=dict(t=40, b=30))
st.plotly_chart(fig_trend, use_container_width=True)

st.markdown("---")

# ── Session table with delete ──────────────────────────────────────────────────
st.subheader("All Sessions")

for s in sessions:
    col_d, col_t, col_dur, col_r, col_n, col_del = st.columns([1.5, 2, 1, 1, 3, 0.7])
    col_d.write(s["date"])
    col_t.write(s["type"])
    col_dur.write(f"{s['duration_minutes']} min")
    col_r.write("⭐" * int(s["rating"] or 0))
    col_n.write(s.get("notes") or "—")
    if col_del.button("🗑", key=f"del_{s['id']}", help="Delete this session"):
        delete_practice_session(int(s["id"]))
        st.rerun()
