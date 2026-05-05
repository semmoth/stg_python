"""
Course Admin — update hole par and distance values for each course.
Only needed once to set up Gullbringa correctly.
"""
import streamlit as st
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
import pandas as pd
import re
from PIL import Image
import io
import numpy as np

from db.queries import get_courses, get_course_tee_names, get_holes, update_hole, create_course, create_holes_for_course
from utils.constants import TEES

# ── OCR functionality for course photos ────────────────────────────────────────
@st.cache_resource
def get_ocr_reader():
    """Lazy load OCR reader to avoid import errors if not installed."""
    try:
        import easyocr
        return easyocr.Reader(['en'])
    except ImportError:
        st.warning("OCR not available. Install with: pip install easyocr")
        return None


def extract_course_data_from_image(image) -> list[tuple]:
    """Extract hole data from scorecard photo using OCR."""
    reader = get_ocr_reader()
    if not reader:
        return []

    # Convert PIL image to format easyocr can handle
    img_array = np.array(image)

    # Get text from image
    results = reader.readtext(img_array)

    # Extract text
    text = " ".join([result[1] for result in results])

    # Look for patterns like "Hole 1: Par 4, 350m" or "1 4 350"
    holes_data = []
    lines = text.split('\n')

    # Pattern 1: "Hole X: Par Y, ZZZm"
    hole_pattern1 = r'Hole\s*(\d+).*?Par\s*(\d+).*?(\d+)\s*m'
    # Pattern 2: "X Y ZZZ" (hole par distance)
    hole_pattern2 = r'(\d+)\s+(\d+)\s+(\d+)'

    for line in lines:
        # Try pattern 1
        match1 = re.search(hole_pattern1, line, re.IGNORECASE)
        if match1:
            hole_num, par, distance = map(int, match1.groups())
            holes_data.append((hole_num, par, distance))
            continue

        # Try pattern 2
        match2 = re.search(hole_pattern2, line)
        if match2 and len(holes_data) < 18:  # Limit to 18 holes
            hole_num, par, distance = map(int, match2.groups())
            if 1 <= hole_num <= 18 and 3 <= par <= 5 and 50 <= distance <= 700:
                holes_data.append((hole_num, par, distance))

    # Sort by hole number and return unique holes
    holes_data = list(set(holes_data))  # Remove duplicates
    holes_data.sort(key=lambda x: x[0])

    return holes_data[:18]  # Limit to 18 holes

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
st.title("⚙️ Course Admin")

# ── Create New Course ──────────────────────────────────────────────────────────
st.header("🏌️ Create New Course")

with st.expander("Add New Course", expanded=False):
    col1, col2 = st.columns([1, 1])

    with col1:
        club_name = st.text_input("Club Name", placeholder="e.g., Gullbringa Golf Club")
        course_name = st.text_input("Course Name", placeholder="e.g., Gullbringa Golf and Country Club")
        course_location = st.text_input("Location (optional)", placeholder="e.g., Hönö, Sweden")
        create_tee = st.selectbox("Tee for this data", TEES + ["Other"], index=0, help="Which tee set are you creating?")
        custom_tee = None
        if create_tee == "Other":
            custom_tee = st.text_input("Custom tee name", placeholder="e.g. Blue, Back, Tournament")
        tee_name = custom_tee.strip() if create_tee == "Other" and custom_tee else create_tee

    with col2:
        st.markdown("**Option 1: Upload Course Photo**")
        uploaded_file = st.file_uploader(
            "Upload a photo of the scorecard or course layout",
            type=["jpg", "jpeg", "png"],
            help="OCR will try to extract hole information from the image"
        )

        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Image", width=300)

            if st.button("Extract Data from Photo"):
                with st.spinner("Analyzing image..."):
                    extracted_data = extract_course_data_from_image(image)

                if extracted_data:
                    st.success(f"Found {len(extracted_data)} holes!")
                    df_extracted = pd.DataFrame(extracted_data, columns=["Hole", "Par", "Distance (m)"])
                    st.dataframe(df_extracted, hide_index=True)

                    if st.button("Create Course from Extracted Data"):
                        if not course_name.strip():
                            st.warning("Enter a course name.")
                        elif create_tee == "Other" and not custom_tee:
                            st.warning("Enter a custom tee name.")
                        else:
                            try:
                                course_id = create_course(course_name.strip(), course_location.strip(), club_name.strip() or None)
                                create_holes_for_course(course_id, extracted_data, tee_name)
                                st.success(f"Course '{course_name}' created with {len(extracted_data)} holes for {tee_name} tee!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error creating course: {e}")
                else:
                    st.warning("Could not extract hole data from the image. Try a clearer photo or use manual entry below.")

    st.markdown("---")
    st.markdown("**Option 2: Manual Entry**")

    hole_inputs = []
    hole_cols = st.columns(3)
    for hole_num in range(1, 19):
        col = hole_cols[(hole_num - 1) % 3]
        with col:
            st.markdown(f"**Hole {hole_num}**")
            par_val = st.selectbox(
                "Par", [3, 4, 5],
                index=1,
                key=f"manual_par_{hole_num}",
            )
            dist_val = st.number_input(
                "Distance (m)",
                min_value=50, max_value=700,
                value=300,
                step=5,
                key=f"manual_dist_{hole_num}",
            )
            hole_inputs.append((hole_num, par_val, dist_val))

    if st.button("Create Course from Manual Entry"):
        if not course_name.strip():
            st.warning("Enter a course name.")
        elif create_tee == "Other" and not custom_tee:
            st.warning("Enter a custom tee name.")
        else:
            try:
                course_id = create_course(course_name.strip(), course_location.strip(), club_name.strip() or None)
                create_holes_for_course(course_id, hole_inputs, tee_name)
                st.success(f"Course '{course_name.strip()}' created with 18 holes for {tee_name} tee!")
                st.rerun()
            except Exception as e:
                st.error(f"Error creating course: {e}")

    if st.button("Add 18 Standard Holes"):
        if not course_name.strip():
            st.warning("Enter a course name.")
        elif create_tee == "Other" and not custom_tee:
            st.warning("Enter a custom tee name.")
        else:
            default_holes = [(i, 4, 350) for i in range(1, 19)]  # Default par 4, 350m
            try:
                course_id = create_course(course_name.strip(), course_location.strip(), club_name.strip() or None)
                create_holes_for_course(course_id, default_holes, tee_name)
                st.success(f"Course '{course_name.strip()}' created with 18 default holes for {tee_name} tee!")
                st.rerun()
            except Exception as e:
                st.error(f"Error creating course: {e}")

st.markdown("---")

# ── Edit Existing Courses ──────────────────────────────────────────────────────
st.header("📝 Edit Existing Courses")
st.info("Update the par and distance for each hole. Changes take effect immediately.")

courses = get_courses()
if not courses:
    st.error("No courses found. Run setup_db.py first.")
    st.stop()

# ── Course Overview ───────────────────────────────────────────────────────────
st.subheader("Course Overview")
courses_df = pd.DataFrame([
    {
        "Club": c.get("club", ""),
        "Course Name": c["name"],
        "Location": c.get("location", ""),
        "Holes": c["nr_of_holes"]
    }
    for c in courses
])
st.dataframe(courses_df, use_container_width=True, hide_index=True)

st.markdown("---")

course_names = [c["name"] for c in courses]
selected_name = st.selectbox("Select Course to Edit", course_names)
course = next(c for c in courses if c["name"] == selected_name)

# Tee selection
existing_tees = get_course_tee_names(int(course["id"]))
if not existing_tees:
    existing_tees = TEES
tee_options = existing_tees + ["Other"]
selected_tee = st.selectbox("Tee", tee_options, index=0)
custom_tee = None
if selected_tee == "Other":
    custom_tee = st.text_input("Custom tee name", placeholder="e.g. Blue, Back, Tournament")
tee_name = custom_tee.strip() if custom_tee else selected_tee

holes = get_holes(int(course["id"]), tee_name=tee_name)

if not holes:
    st.warning("No holes found for this course.")
    st.stop()

st.subheader(f"{selected_name} — {selected_tee} Tee — {course['nr_of_holes']} Holes")
st.markdown("Edit par and distance for each hole, then click **Save All Changes**.")

# Build editable form
updated = {}
cols_per_row = 3
rows = [holes[i:i+cols_per_row] for i in range(0, len(holes), cols_per_row)]

for row in rows:
    cols = st.columns(cols_per_row)
    for col, hole in zip(cols, row):
        with col:
            st.markdown(f"**Hole {hole['hole_number']}**")
            par_val = st.selectbox(
                "Par", [3, 4, 5],
                index=[3, 4, 5].index(int(hole["par"])),
                key=f"par_{hole['id']}",
            )
            dist_val = st.number_input(
                "Distance (m)",
                min_value=50, max_value=650,
                value=int(hole["distance"]) if hole["distance"] else 300,
                step=5,
                key=f"dist_{hole['id']}",
            )
            updated[hole["id"]] = (par_val, dist_val)

if st.button("Save All Changes", type="primary", use_container_width=True):
    for hole_id, (par, dist) in updated.items():
        update_hole(hole_id, par, dist, tee_name=tee_name)
    st.success(f"All {tee_name} tee holes updated!")
    st.rerun()

# ── Preview table ──────────────────────────────────────────────────────────────
import pandas as pd
df = pd.DataFrame([
    {"Hole": h["hole_number"], "Par": h["par"], "Distance (m)": h["distance"]}
    for h in holes
])
st.dataframe(df, use_container_width=True, hide_index=True)
st.caption(f"Total par: {df['Par'].sum()} | Tee: {selected_tee}")
