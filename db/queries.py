"""All database query functions."""
from db.client import get_client


# ── Tees ────────────────────────────────────────────────────────────────────────

def get_tees() -> list[dict]:
    """Get all available tees."""
    return get_client().fetchall("SELECT id, name FROM tees ORDER BY name")


def get_tee_id(tee_name: str) -> int | None:
    """Get tee ID by name, return None if not found."""
    result = get_client().fetchone("SELECT id FROM tees WHERE name = ?", [tee_name])
    return int(result["id"]) if result else None


def create_tee(name: str) -> int:
    """Create a new tee."""
    return get_client().execute("INSERT INTO tees (name) VALUES (?)", [name])


# ── Courses & Holes ────────────────────────────────────────────────────────────────────────────────────

def get_courses() -> list[dict]:
    return get_client().fetchall("""
        SELECT c.*, COUNT(h.id) as nr_of_holes
        FROM courses c
        LEFT JOIN holes h ON c.id = h.course_id
        GROUP BY c.id, c.name, c.location
        ORDER BY c.name
    """)


def create_course(name: str, location: str = "", club: str | None = None) -> int:
    return get_client().execute(
        "INSERT INTO courses (name, location, club) VALUES (?, ?, ?)",
        [name, location, club],
    )


# ── Tournaments ────────────────────────────────────────────────────────────────

def create_tournament(name: str, course_id: int, tee: str, start_date: str, end_date: str) -> int:
    try:
        return get_client().execute(
            "INSERT INTO tournaments (name, course_id, tee, start_date, end_date) VALUES (?, ?, ?, ?, ?)",
            [name, course_id, tee, start_date, end_date],
        )
    except Exception as e:
        raise RuntimeError(f"Tournament table may not exist. Run setup_db.py first. Error: {e}")


def get_tournaments() -> list[dict]:
    try:
        return get_client().fetchall(
            """
            SELECT t.*, c.name as course_name
            FROM tournaments t
            JOIN courses c ON c.id = t.course_id
            ORDER BY t.start_date DESC, t.name
            """
        )
    except Exception:
        return []


def get_tournament(tournament_id: int) -> dict | None:
    try:
        return get_client().fetchone(
            """
            SELECT t.*, c.name as course_name
            FROM tournaments t
            JOIN courses c ON c.id = t.course_id
            WHERE t.id = ?
            """,
            [tournament_id],
        )
    except Exception:
        return None


# ── Course Tee Management ──────────────────────────────────────────────────────

def get_course_tee_names(course_id: int) -> list[str]:
    """Get all tee names available for a course."""
    rows = get_client().fetchall(
        "SELECT DISTINCT tee_name FROM hole_tees WHERE course_id = ? ORDER BY tee_name",
        [course_id],
    )
    return [row["tee_name"] for row in rows if row.get("tee_name")]


def get_course_tee_id(course_id: int, tee_name: str) -> int:
    """Get or create a tee_id for a course and tee_name combination."""
    # Try to find existing tee_id for this tee_name
    existing = get_client().fetchone(
        "SELECT tee_id FROM hole_tees WHERE course_id = ? AND tee_name = ? LIMIT 1",
        [course_id, tee_name],
    )
    if existing and existing.get("tee_id") is not None:
        return int(existing["tee_id"])

    # Try to look up tee by name in tees table
    tee_result = get_client().fetchone("SELECT id FROM tees WHERE name = ?", [tee_name])
    if tee_result:
        return int(tee_result["id"])

    # If tee doesn't exist, create it
    tee_id = create_tee(tee_name)
    return tee_id


def create_holes_for_course(course_id: int, holes_data: list[tuple], tee_name: str = "Yellow") -> None:
    """Create holes and hole_tees for a course. holes_data: [(hole_number, par, distance), ...]"""
    tee_id = get_course_tee_id(course_id, tee_name)
    for hole_num, par, distance in holes_data:
        hole_id = get_client().execute(
            "INSERT INTO holes (course_id, hole_number) VALUES (?, ?)",
            [course_id, hole_num],
        )
        get_client().execute(
            "INSERT INTO hole_tees (hole_id, course_id, tee_id, tee_name, par, distance, hole_number) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [hole_id, course_id, tee_id, tee_name, par, distance, hole_num],
        )


def get_holes(course_id: int, tee_name: str) -> list[dict]:
    """Get all holes for a course and tee."""
    return get_client().fetchall(
        "SELECT h.id, h.hole_number, ht.par, ht.distance FROM holes h INNER JOIN hole_tees ht ON h.id = ht.hole_id WHERE h.course_id = ? AND ht.tee_name = ? ORDER BY h.hole_number",
        [course_id, tee_name],
    )


def get_hole(course_id: int, hole_number: int, tee_name: str) -> dict | None:
    """Get a specific hole for a course, hole number, and tee."""
    return get_client().fetchone(
        "SELECT h.id, h.hole_number, ht.par, ht.distance FROM holes h INNER JOIN hole_tees ht ON h.id = ht.hole_id WHERE h.course_id = ? AND h.hole_number = ? AND ht.tee_name = ?",
        [course_id, hole_number, tee_name],
    )


def update_hole(hole_id: int, par: int, distance: int, tee_name: str):
    """Update par and distance for a hole tee."""
    get_client().execute(
        "UPDATE hole_tees SET par = ?, distance = ? WHERE hole_id = ? AND tee_name = ?",
        [par, distance, hole_id, tee_name],
    )


# ── Rounds ─────────────────────────────────────────────────────────────────────

def create_round(username: str, course_id: int, date: str, tee: str, tournament_id: int | None = None) -> int:
    return get_client().execute(
        "INSERT INTO rounds (username, course_id, date, tee, tournament_id) VALUES (?, ?, ?, ?, ?)",
        [username, course_id, date, tee, tournament_id],
    )


def get_rounds(username: str) -> list[dict]:
    return get_client().fetchall(
        """
        SELECT r.*, c.name as course_name, t.name as tournament_name
        FROM rounds r
        JOIN courses c ON c.id = r.course_id
        LEFT JOIN tournaments t ON t.id = r.tournament_id
        WHERE r.username = ?
        ORDER BY r.date DESC
        """,
        [username],
    )


def get_round(round_id: int) -> dict | None:
    return get_client().fetchone(
        """
        SELECT r.*, c.name as course_name, t.name as tournament_name
        FROM rounds r
        JOIN courses c ON c.id = r.course_id
        LEFT JOIN tournaments t ON t.id = r.tournament_id
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
            None,
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


# ── Practice Log ───────────────────────────────────────────────────────────────

def _ensure_practice_table():
    get_client().execute("""
        CREATE TABLE IF NOT EXISTS practice_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            duration_minutes INTEGER,
            notes TEXT,
            rating INTEGER
        )
    """)


def create_practice_session(
    username: str, date: str, type: str,
    duration_minutes: int | None, notes: str | None, rating: int | None,
) -> int:
    _ensure_practice_table()
    return get_client().execute(
        "INSERT INTO practice_sessions (username, date, type, duration_minutes, notes, rating) VALUES (?, ?, ?, ?, ?, ?)",
        [username, date, type, duration_minutes, notes, rating],
    )


def get_practice_sessions(username: str) -> list[dict]:
    _ensure_practice_table()
    return get_client().fetchall(
        "SELECT * FROM practice_sessions WHERE username = ? ORDER BY date DESC",
        [username],
    )


def delete_practice_session(session_id: int):
    _ensure_practice_table()
    get_client().execute("DELETE FROM practice_sessions WHERE id = ?", [session_id])


def get_all_shots_for_user(username: str) -> list[dict]:
    """Get all completed shots for a user with course and hole data."""
    return get_client().fetchall(
        """
        SELECT s.*, r.date, r.course_id, r.tee, c.name as course_name,
               ht.par, ht.distance
        FROM shots s
        JOIN rounds r ON r.id = s.round_id
        JOIN courses c ON c.id = r.course_id
        JOIN holes h ON h.course_id = r.course_id AND h.hole_number = s.hole_number
        JOIN hole_tees ht ON ht.hole_id = h.id AND ht.tee_name = r.tee
        WHERE r.username = ? AND r.completed = 1
        ORDER BY r.date DESC, s.hole_number, s.shot_number
        """,
        [username],
    )
