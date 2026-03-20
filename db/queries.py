"""All database query functions."""
from db.client import get_client


# ── Courses & Holes ────────────────────────────────────────────────────────────

def get_courses() -> list[dict]:
    return get_client().fetchall("SELECT * FROM courses ORDER BY name")


def get_holes(course_id: int) -> list[dict]:
    return get_client().fetchall(
        "SELECT * FROM holes WHERE course_id = ? ORDER BY hole_number",
        [course_id],
    )


def get_hole(course_id: int, hole_number: int) -> dict | None:
    return get_client().fetchone(
        "SELECT * FROM holes WHERE course_id = ? AND hole_number = ?",
        [course_id, hole_number],
    )


def update_hole(hole_id: int, par: int, distance: int):
    get_client().execute(
        "UPDATE holes SET par = ?, distance_meters = ? WHERE id = ?",
        [par, distance, hole_id],
    )


# ── Rounds ─────────────────────────────────────────────────────────────────────

def create_round(username: str, course_id: int, date: str, tee: str) -> int:
    return get_client().execute(
        "INSERT INTO rounds (username, course_id, date, tee) VALUES (?, ?, ?, ?)",
        [username, course_id, date, tee],
    )


def get_rounds(username: str) -> list[dict]:
    return get_client().fetchall(
        """
        SELECT r.*, c.name as course_name
        FROM rounds r
        JOIN courses c ON c.id = r.course_id
        WHERE r.username = ?
        ORDER BY r.date DESC
        """,
        [username],
    )


def get_round(round_id: int) -> dict | None:
    return get_client().fetchone(
        """
        SELECT r.*, c.name as course_name
        FROM rounds r
        JOIN courses c ON c.id = r.course_id
        WHERE r.id = ?
        """,
        [round_id],
    )


def complete_round(round_id: int):
    get_client().execute(
        "UPDATE rounds SET completed = 1 WHERE id = ?",
        [round_id],
    )


def delete_round(round_id: int):
    get_client().execute("DELETE FROM shots WHERE round_id = ?", [round_id])
    get_client().execute("DELETE FROM rounds WHERE id = ?", [round_id])


# ── Shots ──────────────────────────────────────────────────────────────────────

def save_shot(
    round_id: int,
    hole_number: int,
    shot_number: int,
    surface: str,
    distance_to_hole: float,
    distance_unit: str,
    club: str | None,
    shot_distance: float | None,
    holed: bool,
) -> int:
    return get_client().execute(
        """
        INSERT INTO shots (
            round_id, hole_number, shot_number, surface,
            distance_to_hole, distance_unit,
            club, shot_distance, holed
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            round_id, hole_number, shot_number, surface,
            distance_to_hole, distance_unit,
            club, shot_distance, int(holed),
        ],
    )


def get_shots_for_round(round_id: int) -> list[dict]:
    return get_client().fetchall(
        """
        SELECT * FROM shots
        WHERE round_id = ?
        ORDER BY hole_number, shot_number
        """,
        [round_id],
    )


def get_shots_for_hole(round_id: int, hole_number: int) -> list[dict]:
    return get_client().fetchall(
        """
        SELECT * FROM shots
        WHERE round_id = ? AND hole_number = ?
        ORDER BY shot_number
        """,
        [round_id, hole_number],
    )


def delete_shots_for_hole(round_id: int, hole_number: int):
    get_client().execute(
        "DELETE FROM shots WHERE round_id = ? AND hole_number = ?",
        [round_id, hole_number],
    )


def get_all_shots_for_user(username: str) -> list[dict]:
    return get_client().fetchall(
        """
        SELECT s.*, r.date, r.course_id, r.tee, c.name as course_name,
               h.par, h.distance_meters
        FROM shots s
        JOIN rounds r ON r.id = s.round_id
        JOIN courses c ON c.id = r.course_id
        JOIN holes h ON h.course_id = r.course_id AND h.hole_number = s.hole_number
        WHERE r.username = ? AND r.completed = 1
        ORDER BY r.date DESC, s.hole_number, s.shot_number
        """,
        [username],
    )
