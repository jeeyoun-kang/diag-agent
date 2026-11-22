import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from src.config import DATA_DIR, DB_PATH

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

UPDATABLE_COLUMNS = {
    "diagnosis",
    "tool_calls_json",
    "action_proposed",
    "action_approved",
    "action_taken",
    "post_check_value",
    "diagnosis_correct",
    "resolved_at",
}


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """성공 시 커밋, 예외 시 롤백하고 항상 연결을 닫는다.

    sqlite3.Connection 자체의 with 문은 커밋/롤백만 하고 닫지 않으므로,
    오래 도는 모니터링 루프에서 연결이 쌓이지 않도록 직접 닫는다.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


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


def update_incident(incident_id: int, **fields) -> None:
    unknown = set(fields) - UPDATABLE_COLUMNS
    if unknown:
        raise ValueError(f"unknown incident columns: {sorted(unknown)}")
    if not fields:
        return
    assignments = ", ".join(f"{column} = ?" for column in fields)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE incidents SET {assignments} WHERE id = ?",
            (*fields.values(), incident_id),
        )


def get_open_incident(trigger_metric: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM incidents WHERE trigger_metric = ? AND resolved_at IS NULL "
            "ORDER BY id DESC LIMIT 1",
            (trigger_metric,),
        ).fetchone()


def get_incident(incident_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
