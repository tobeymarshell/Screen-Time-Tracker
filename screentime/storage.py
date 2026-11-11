"""SQLite persistence, queries, and path management."""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path


def data_dir() -> Path:
    """Returns application data directory under %LOCALAPPDATA%."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    p = Path(base) / "ScreenTimeTracker"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_db_path() -> Path:
    """Returns default database path."""
    return data_dir() / "tracker.db"


def load_pos():
    """Loads saved widget screen coordinates."""
    try:
        with open(data_dir() / "pos.json", "r") as f:
            d = json.load(f)
            return int(d.get("x")), int(d.get("y"))
    except Exception:
        return None, None


def save_pos(x: int, y: int):
    """Saves widget screen coordinates."""
    try:
        with open(data_dir() / "pos.json", "w") as f:
            json.dump({"x": int(x), "y": int(y)}, f)
    except Exception:
        pass


def init_db(conn: sqlite3.Connection):
    """Initializes tables and indexing in WAL mode."""
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, app_name TEXT NOT NULL,
        window_title TEXT, start_time TEXT NOT NULL, end_time TEXT NOT NULL,
        duration_seconds INTEGER NOT NULL)"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions(start_time)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sessions_day ON"
        " sessions(substr(start_time,1,10))"
    )
    conn.commit()


def save_session(
    conn: sqlite3.Connection,
    app: str,
    title: str,
    start: float,
    end: float,
):
    """Saves an active tracking session. Redacts window title for privacy."""
    dur = int(end - start)
    if dur < 1 or not app:
        return
    conn.execute(
        "INSERT INTO sessions (app_name, window_title, start_time, end_time,"
        " duration_seconds) VALUES (?,?,?,?,?)",
        (
            app,
            "",
            datetime.fromtimestamp(start).isoformat(timespec="seconds"),
            datetime.fromtimestamp(end).isoformat(timespec="seconds"),
            dur,
        ),
    )
    conn.commit()


def query_daily_total(conn: sqlite3.Connection, target_date) -> int:
    """Returns total active seconds for a target date (date object or str)."""
    day_str = (
        target_date.isoformat()[:10]
        if hasattr(target_date, "isoformat")
        else str(target_date)[:10]
    )
    return conn.execute(
        "SELECT COALESCE(SUM(duration_seconds),0) FROM sessions WHERE"
        " substr(start_time,1,10) = ?",
        (day_str,),
    ).fetchone()[0]


def query_top_apps(conn: sqlite3.Connection, target_date):
    """Returns top applications and durations for a target date."""
    day_str = (
        target_date.isoformat()[:10]
        if hasattr(target_date, "isoformat")
        else str(target_date)[:10]
    )
    return conn.execute(
        "SELECT app_name, SUM(duration_seconds) AS total FROM sessions WHERE"
        " substr(start_time,1,10) = ? GROUP BY app_name ORDER BY total DESC",
        (day_str,),
    ).fetchall()


def query_daily_totals_range(conn: sqlite3.Connection, start_date, end_date):
    """Returns daily aggregations over a date range."""
    start_str = (
        start_date.isoformat()[:10]
        if hasattr(start_date, "isoformat")
        else str(start_date)[:10]
    )
    end_str = (
        end_date.isoformat()[:10]
        if hasattr(end_date, "isoformat")
        else str(end_date)[:10]
    )
    return conn.execute(
        "SELECT substr(start_time,1,10) AS day, SUM(duration_seconds) FROM"
        " sessions WHERE substr(start_time,1,10) >= ? AND"
        " substr(start_time,1,10) <= ? GROUP BY day ORDER BY day",
        (start_str, end_str),
    ).fetchall()


def open_db_readonly(path) -> sqlite3.Connection:
    """Opens a SQLite connection in read-only mode."""
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
