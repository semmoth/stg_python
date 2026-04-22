"""All database query functions."""
from db.client import get_client


# ── Courses & Holes ────────────────────────────────────────────────────────────

def get_courses() -> list[dict]:
    return get_client().fetchall("""
        SELECT c.*, COUNT(h.id) as nr_of_holes
        FROM courses c
        LEFT JOIN holes h ON c.id = h.course_id
        GROUP BY c.id, c.name, c.location
        ORDER BY c.name
    """)


def create_course(name: str, location: str = "") -> int:
    return get_client().execute(
        "INSERT INTO courses (name, location) VALUES (?, ?)",
        [name, location],
    )


def create_holes_for_course(course_id: int, holes_data: list[tuple], tee_id: int = 1) -> None:
    """Create holes and hole_tees for a course. holes_data: [(hole_number, par, distance), ...]"""
    for hole_num, par, distance in holes_data:
        # Create hole
        hole_id = get_client().execute(
            "INSERT INTO holes (course_id, hole_number) VALUES (?, ?)",
            [course_id, hole_num],
        )
        # Create hole_tee
        get_client().execute(
            "INSERT INTO hole_tees (hole_id, course_id, tee_id, par, distance) VALUES (?, ?, ?, ?, ?)",
            [hole_id, course_id, tee_id, par, distance],
        )


def get_holes(course_id: int, tee_id: int = 1) -> list[dict]:
    return get_client().fetchall(
        "SELECT h.id, h.hole_number, ht.par, ht.distance FROM holes h INNER JOIN hole_tees ht ON h.id = ht.hole_id WHERE h.course_id = ? AND ht.tee_id = ? ORDER BY h.hole_number",
        [course_id, tee_id],
    )


def get_hole(course_id: int, hole_number: int, tee_id: int = 1) -> dict | None:
    return get_client().fetchone(
        "SELECT h.id, h.hole_number, ht.par, ht.distance FROM holes h INNER JOIN hole_tees ht ON h.id = ht.hole_id WHERE h.course_id = ? AND h.hole_number = ? AND ht.tee_id = ?",
        [course_id, hole_number, tee_id],
    )


def update_hole(hole_id: int, par: int, distance: int, tee_id: int = 1):
    get_client().execute(
        "UPDATE hole_tees SET par = ?, distance = ? WHERE hole_id = ? AND tee_id = ?",
        [par, distance, hole_id, tee_id],
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
    distance_to_hole: int,
    distance_unit: str,
    club: str | None,
    shot_distance: int | None,
    holed: bool,
    penalty: bool = False,
) -> int:
    return get_client().execute(
        "INSERT INTO shots (round_id, hole_number, shot_number, surface, distance_to_hole, distance_unit, club, shot_distance, holed, penalty) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            round_id,
            hole_number,
            shot_number,
            surface,
            int(distance_to_hole),
            distance_unit,
            club,
            int(shot_distance) if shot_distance else None,
            holed,
            int(penalty),
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
               ht.par, ht.distance
        FROM shots s
        JOIN rounds r ON r.id = s.round_id
        JOIN courses c ON c.id = r.course_id
        JOIN holes h ON h.course_id = r.course_id AND h.hole_number = s.hole_number
        JOIN hole_tees ht ON ht.hole_id = h.id AND ht.tee_id = CASE WHEN r.tee = 'Yellow' THEN 1 ELSE 2 END
        WHERE r.username = ? AND r.completed = 1
        ORDER BY r.date DESC, s.hole_number, s.shot_number
        """,
        [username],
    )
