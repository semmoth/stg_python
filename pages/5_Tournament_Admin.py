"""
Tournament Admin page.
Create tournaments and review the schedule for multi-day / multi-round events.
"""
import streamlit as st
from datetime import date
import pandas as pd

from db.queries import get_courses, get_course_tee_names, get_tournaments, create_tournament
from utils.constants import TEES

# ── Page ───────────────────────────────────────────────────────────────────────
st.title("🏆 Tournament Admin")
st.markdown("Create a tournament with a course, tee set, and a date window. Then choose the tournament when starting a new round in Data Entry.")

courses = get_courses()
if not courses:
    st.error("No courses found. Add a course first in Course Admin.")
    st.stop()

st.header("Create a New Tournament")
with st.form("tournament_form"):
    tournament_name = st.text_input("Tournament name", placeholder="e.g. Club Championship")
    course_names = [c["name"] for c in courses]
    selected_course_name = st.selectbox("Course", course_names)
    selected_course = next(c for c in courses if c["name"] == selected_course_name)
    course_tees = get_course_tee_names(int(selected_course["id"]))
    if not course_tees:
        course_tees = TEES
    selected_tee = st.selectbox("Tee", course_tees + ["Other"])
    custom_tee = None
    if selected_tee == "Other":
        custom_tee = st.text_input("Custom tee name", placeholder="e.g. Blue, Back, Tournament")
    tee_name = custom_tee.strip() if custom_tee else selected_tee

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start date", value=date.today())
    with col2:
        end_date = st.date_input("End date", value=date.today())

    submit = st.form_submit_button("Create Tournament")

    if submit:
        if not tournament_name.strip():
            st.warning("Enter a tournament name.")
        elif end_date < start_date:
            st.warning("End date must be on or after the start date.")
        else:
            create_tournament(
                tournament_name.strip(),
                int(selected_course["id"]),
                tee_name,
                str(start_date),
                str(end_date),
            )
            st.success(f"Tournament '{tournament_name.strip()}' created for {selected_course_name}.")
            st.rerun()

st.markdown("---")

st.header("Scheduled Tournaments")
tournaments = get_tournaments()
if tournaments:
    tournaments_df = pd.DataFrame([
        {
            "Name": t["name"],
            "Course": t["course_name"],
            "Tee": t["tee"],
            "Start": t["start_date"],
            "End": t["end_date"],
        }
        for t in tournaments
    ])
    st.dataframe(tournaments_df, use_container_width=True, hide_index=True)
else:
    st.info("No tournaments created yet.")
