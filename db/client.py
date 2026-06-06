"""
Turso HTTP API client.
Uses the /v2/pipeline endpoint — no binary dependencies, works on all platforms.
"""
import requests
import streamlit as st
from typing import Any


def _arg(value: Any) -> dict:
    """Convert a Python value to a Turso arg dict."""
    if value is None:
        return {"type": "null", "value": None}
    if isinstance(value, bool):
        return {"type": "integer", "value": str(int(value))}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, float):
        return {"type": "float", "value": str(value)}
    return {"type": "text", "value": str(value)}


def _parse_rows(result: dict) -> list[dict]:
    """Parse Turso response rows into list of dicts."""
    cols = [c["name"] for c in result["cols"]]
    rows = []
    for row in result["rows"]:
        record = {}
        for i, col in enumerate(cols):
            cell = row[i]
            record[col] = None if cell["type"] == "null" else cell["value"]
        rows.append(record)
    return rows


class TursoClient:
    def __init__(self):
        try:
            turso_url = st.secrets["TURSO_URL"].rstrip("/")
            self.token = st.secrets["TURSO_TOKEN"]
        except KeyError as e:
            st.error(
                f"Missing database secret: {e}. "
                "Add TURSO_URL and TURSO_TOKEN to your Streamlit secrets."
            )
            st.stop()

        # Convert libsql:// to https:// for HTTP API
        self.url = turso_url.replace("libsql://", "https://")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _pipeline(self, sql: str, params: list = None) -> dict:
        stmt = {"sql": sql, "args": [_arg(p) for p in (params or [])]}
        payload = {
            "requests": [
                {"type": "execute", "stmt": stmt},
                {"type": "close"},
            ]
        }
        try:
            resp = requests.post(
                f"{self.url}/v2/pipeline",
                headers=self.headers,
                json=payload,
                timeout=10,
            )
            resp.raise_for_status()
        except requests.exceptions.ConnectionError:
            st.error("Cannot reach the database. Check your internet connection.")
            st.stop()
        except requests.exceptions.Timeout:
            st.error("Database request timed out. Please try again.")
            st.stop()
        except requests.exceptions.HTTPError as e:
            st.error(f"Database error ({e.response.status_code}). Check your TURSO_TOKEN.")
            st.stop()

        data = resp.json()
        result = data["results"][0]
        if result["type"] == "error":
            raise RuntimeError(result["error"]["message"])
        return result["response"]["result"]

    def execute(self, sql: str, params: list = None) -> int:
        """Execute INSERT/UPDATE/DELETE. Returns last insert rowid."""
        result = self._pipeline(sql, params)
        rowid = result.get("last_insert_rowid")
        return int(rowid) if rowid is not None else None

    def fetchall(self, sql: str, params: list = None) -> list[dict]:
        """Execute SELECT. Returns list of row dicts."""
        return _parse_rows(self._pipeline(sql, params))

    def fetchone(self, sql: str, params: list = None) -> dict | None:
        rows = self.fetchall(sql, params)
        return rows[0] if rows else None


@st.cache_resource
def get_client() -> TursoClient:
    """Cached Turso client — one connection per app session."""
    return TursoClient()
