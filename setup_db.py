"""
One-time database setup script.
Run once after creating your Turso database:
    python setup_db.py

Creates all tables and seeds Gullbringa Golf and Country Club.
"""
import os
import sys

# Allow running from project root
sys.path.insert(0, os.path.dirname(__file__))

# Streamlit secrets are not available outside Streamlit — load manually
import streamlit as st

# Patch secrets from .streamlit/secrets.toml for CLI usage
try:
    import toml
    secrets = toml.load(".streamlit/secrets.toml")
    st.secrets._secrets = secrets
except Exception:
    try:
        import tomllib
        with open(".streamlit/secrets.toml", "rb") as f:
            secrets = tomllib.load(f)
        # Monkey-patch streamlit secrets for CLI
        class _FakeSecrets(dict):
            def __getitem__(self, key):
                return super().__getitem__(key)
        import streamlit.runtime.secrets as _s
        _s.secrets._parse_secrets_file = lambda: secrets
    except Exception as e:
        print(f"Could not load secrets: {e}")
        print("Make sure .streamlit/secrets.toml has TURSO_URL and TURSO_TOKEN")
        sys.exit(1)


import requests

TURSO_URL = secrets["TURSO_URL"].rstrip("/").replace("libsql://", "https://")
TURSO_TOKEN = secrets["TURSO_TOKEN"]
HEADERS = {
    "Authorization": f"Bearer {TURSO_TOKEN}",
    "Content-Type": "application/json",
}


def run_sql(sql: str, params: list = None):
    stmt = {"sql": sql, "args": []}
    if params:
        for p in params:
            if p is None:
                stmt["args"].append({"type": "null", "value": None})
            elif isinstance(p, int):
                stmt["args"].append({"type": "integer", "value": str(p)})
            elif isinstance(p, float):
                stmt["args"].append({"type": "float", "value": str(p)})
            else:
                stmt["args"].append({"type": "text", "value": str(p)})

    payload = {
        "requests": [
            {"type": "execute", "stmt": stmt},
            {"type": "close"},
        ]
    }
    resp = requests.post(f"{TURSO_URL}/v2/pipeline", headers=HEADERS, json=payload, timeout=10)
    resp.raise_for_status()
    result = resp.json()["results"][0]
    if result["type"] == "error":
        raise RuntimeError(result["error"]["message"])
    return result["response"]["result"]


SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL,
    location TEXT
);

CREATE TABLE IF NOT EXISTS holes (
    id               INTEGER PRIMARY KEY,
    course_id        INTEGER NOT NULL REFERENCES courses(id),
    hole_number      INTEGER NOT NULL,
    par              INTEGER NOT NULL DEFAULT 4,
    distance_meters  INTEGER,
    UNIQUE(course_id, hole_number)
);

CREATE TABLE IF NOT EXISTS rounds (
    id         INTEGER PRIMARY KEY,
    username   TEXT NOT NULL,
    course_id  INTEGER NOT NULL REFERENCES courses(id),
    date       TEXT NOT NULL,
    tee        TEXT,
    completed  INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS shots (
    id               INTEGER PRIMARY KEY,
    round_id         INTEGER NOT NULL REFERENCES rounds(id),
    hole_number      INTEGER NOT NULL,
    shot_number      INTEGER NOT NULL,
    surface          TEXT NOT NULL,
    distance_to_hole REAL NOT NULL,
    distance_unit    TEXT NOT NULL DEFAULT 'meters',
    club             TEXT,
    shot_distance    REAL,
    holed            INTEGER DEFAULT 0,
    created_at       TEXT DEFAULT (datetime('now'))
);
"""

# Gullbringa Golf and Country Club — 18 holes
# Par and distances are placeholders. Update them via the Course Admin page in the app.
GULLBRINGA_HOLES = [
    # (hole, par, distance_meters)
    (1,  4, 350),
    (2,  4, 340),
    (3,  3, 170),
    (4,  5, 480),
    (5,  4, 360),
    (6,  3, 150),
    (7,  4, 380),
    (8,  5, 500),
    (9,  4, 320),
    (10, 4, 370),
    (11, 3, 180),
    (12, 5, 490),
    (13, 4, 350),
    (14, 4, 360),
    (15, 3, 160),
    (16, 4, 400),
    (17, 5, 480),
    (18, 4, 340),
]


def setup():
    print("Creating tables...")
    for stmt in SCHEMA.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            run_sql(stmt)
    print("  Tables created.")

    # Insert course if not exists
    existing = run_sql("SELECT id FROM courses WHERE name = 'Gullbringa Golf and Country Club'")
    if not existing["rows"]:
        run_sql(
            "INSERT INTO courses (name, location) VALUES (?, ?)",
            ["Gullbringa Golf and Country Club", "Hönö, Sweden"],
        )
        print("  Course 'Gullbringa Golf and Country Club' created.")
    else:
        print("  Course already exists — skipping.")

    course_result = run_sql("SELECT id FROM courses WHERE name = 'Gullbringa Golf and Country Club'")
    course_id = int(course_result["rows"][0][0]["value"])

    existing_holes = run_sql("SELECT id FROM holes WHERE course_id = ?", [course_id])
    if not existing_holes["rows"]:
        for hole_num, par, dist in GULLBRINGA_HOLES:
            run_sql(
                "INSERT INTO holes (course_id, hole_number, par, distance_meters) VALUES (?, ?, ?, ?)",
                [course_id, hole_num, par, dist],
            )
        print(f"  18 holes seeded for Gullbringa (placeholder distances — update via Course Admin).")
    else:
        print("  Holes already exist — skipping.")

    print("\nSetup complete!")
    print("Next steps:")
    print("  1. Run the app: streamlit run app.py")
    print("  2. Go to Course Admin to update actual par/distance values for each hole.")
    print("  3. Run hash_password.py to generate hashed passwords, then update config.yaml.")


if __name__ == "__main__":
    setup()
