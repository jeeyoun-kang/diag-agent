import sqlite3
from pathlib import Path

from src.config import DATA_DIR, DB_PATH

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def insert_incident(triggered_at: str, trigger_metric: str, trigger_value: float) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO incidents (triggered_at, trigger_metric, trigger_value) VALUES (?, ?, ?)",
            (triggered_at, trigger_metric, trigger_value),
        )
        return cur.lastrowid
