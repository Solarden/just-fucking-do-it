"""SQLite database layer.

Only service.py should import this module.  Returns raw dicts/tuples;
the service layer converts them into model dataclasses.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

DATA_DIR = Path.home() / ".jfdi"
DB_PATH = DATA_DIR / "jfdi.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS exercises (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    daily_goal  INTEGER NOT NULL DEFAULT 100,
    active      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_id INTEGER NOT NULL REFERENCES exercises(id),
    reps        INTEGER NOT NULL,
    logged_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    text       TEXT    NOT NULL,
    category   TEXT    NOT NULL CHECK(category IN ('nudge', 'completion', 'quote')),
    is_builtin INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sounds (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL UNIQUE,
    path       TEXT    NOT NULL,
    is_default INTEGER NOT NULL DEFAULT 0
);
"""

_DEFAULT_EXERCISES = [
    ("pushups", 100),
    ("crunches", 100),
]

_DEFAULT_CONFIG = {
    "interval": "30",
    "sound_enabled": "1",
    "quiet_hours_start": "8",
    "quiet_hours_end": "22",
    "alias:p": "pushups",
    "alias:c": "crunches",
}

_DEFAULT_MESSAGES = [
    ("DO IT! JUST DO IT!", "quote", 1),
    ("Don't let your dreams be dreams!", "quote", 1),
    ("Yesterday you said tomorrow!", "quote", 1),
    ("NOTHING IS IMPOSSIBLE!", "quote", 1),
    ("MAKE YOUR DREAMS COME TRUE!", "quote", 1),
    ("What are you waiting for?! DO IT!", "quote", 1),
    ("Some people dream of success... you're gonna wake up and work HARD at it!", "quote", 1),
    ("STOP WHAT YOU'RE DOING AND DROP AND GIVE ME 20!", "nudge", 1),
    ("Your muscles are waiting. GO.", "nudge", 1),
    ("You're not tired, you're lazy. MOVE.", "nudge", 1),
    ("Get off your ass. NOW.", "nudge", 1),
    ("You absolute legend.", "completion", 1),
    ("Mission accomplished. Shia is proud.", "completion", 1),
    ("ALL GOALS CRUSHED. You're a machine.", "completion", 1),
]


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------


class Database:
    """Encapsulates a database path and its initialization state."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or DB_PATH
        self._initialized = False

    @property
    def path(self) -> Path:
        return self._path

    @property
    def initialized(self) -> bool:
        return self._initialized

    @contextmanager
    def get_conn(self) -> Iterator[sqlite3.Connection]:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_db(self) -> None:
        """Create tables and seed default data if needed."""
        if self._initialized:
            return
        with self.get_conn() as conn:
            conn.executescript(_SCHEMA)

            # Seed exercises
            for name, goal in _DEFAULT_EXERCISES:
                conn.execute(
                    "INSERT OR IGNORE INTO exercises (name, daily_goal) VALUES (?, ?)",
                    (name, goal),
                )

            # Seed config
            for key, value in _DEFAULT_CONFIG.items():
                conn.execute(
                    "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
                    (key, value),
                )

            # Seed messages
            existing = conn.execute("SELECT COUNT(*) FROM messages WHERE is_builtin = 1").fetchone()[0]
            if existing == 0:
                conn.executemany(
                    "INSERT INTO messages (text, category, is_builtin) VALUES (?, ?, ?)",
                    _DEFAULT_MESSAGES,
                )

        self._initialized = True


# Module-level default instance for production use.
_default = Database()


# ---------------------------------------------------------------------------
# Backward-compat wrappers (delegates to _default instance)
# ---------------------------------------------------------------------------


def set_db_path(path: Path | None) -> None:
    """Override the DB path.  Replaces the default Database instance."""
    global _default
    _default = Database(path)


def get_conn() -> Iterator[sqlite3.Connection]:
    """Context manager — delegates to the default Database instance."""
    return _default.get_conn()


def init_db() -> None:
    """Delegates to the default Database instance."""
    _default.init_db()


def is_initialized() -> bool:
    return _default.initialized


# ---------------------------------------------------------------------------
# Exercises
# ---------------------------------------------------------------------------

def get_active_exercises(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, name, daily_goal FROM exercises WHERE active = 1 ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


def get_exercise_by_name(conn: sqlite3.Connection, name: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT id, name, daily_goal, active FROM exercises WHERE name = ?", (name,)
    ).fetchone()
    return dict(row) if row else None


def add_exercise(conn: sqlite3.Connection, name: str, goal: int) -> int:
    cur = conn.execute(
        "INSERT INTO exercises (name, daily_goal) VALUES (?, ?) "
        "ON CONFLICT(name) DO UPDATE SET daily_goal = ?, active = 1",
        (name, goal, goal),
    )
    return cur.lastrowid  # type: ignore[return-value]


def deactivate_exercise(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute("UPDATE exercises SET active = 0 WHERE name = ? AND active = 1", (name,))
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------

def insert_log(conn: sqlite3.Connection, exercise_id: int, reps: int) -> int:
    cur = conn.execute(
        "INSERT INTO logs (exercise_id, reps) VALUES (?, ?)",
        (exercise_id, reps),
    )
    return cur.lastrowid  # type: ignore[return-value]


def get_today_logs(conn: sqlite3.Connection, exercise_id: int, today: str | None = None) -> list[dict[str, Any]]:
    if today is None:
        today = datetime.now().strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT id, reps, logged_at FROM logs "
        "WHERE exercise_id = ? AND date(logged_at) = ? ORDER BY logged_at",
        (exercise_id, today),
    ).fetchall()
    return [dict(r) for r in rows]


def get_today_total(conn: sqlite3.Connection, exercise_id: int, today: str | None = None) -> int:
    if today is None:
        today = datetime.now().strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT COALESCE(SUM(reps), 0) AS total FROM logs "
        "WHERE exercise_id = ? AND date(logged_at) = ?",
        (exercise_id, today),
    ).fetchone()
    return row[0]


def delete_last_log(conn: sqlite3.Connection) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT l.id, l.reps, e.name FROM logs l "
        "JOIN exercises e ON l.exercise_id = e.id "
        "ORDER BY l.id DESC LIMIT 1"
    ).fetchone()
    if row:
        conn.execute("DELETE FROM logs WHERE id = ?", (row["id"],))
        return dict(row)
    return None


def get_daily_totals(conn: sqlite3.Connection, days: int = 7) -> list[dict[str, Any]]:
    """Returns rows of (date, exercise_name, daily_goal, total_reps)."""
    rows = conn.execute(
        """
        SELECT date(l.logged_at) AS day, e.name, e.daily_goal,
               SUM(l.reps) AS total
        FROM logs l
        JOIN exercises e ON l.exercise_id = e.id
        WHERE l.logged_at >= date('now', 'localtime', ?)
        GROUP BY day, e.name
        ORDER BY day DESC, e.name
        """,
        (f"-{days} days",),
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_logs_for_export(conn: sqlite3.Connection, days: int | None = None) -> list[dict[str, Any]]:
    query = """
        SELECT date(l.logged_at) AS day, e.name AS exercise, l.reps,
               e.daily_goal AS goal, l.logged_at
        FROM logs l
        JOIN exercises e ON l.exercise_id = e.id
    """
    params: tuple[Any, ...] = ()
    if days is not None:
        query += " WHERE l.logged_at >= date('now', 'localtime', ?)"
        params = (f"-{days} days",)
    query += " ORDER BY l.logged_at"
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def get_config_value(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def set_config_value(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO config (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = ?",
        (key, value, value),
    )


def delete_config_key(conn: sqlite3.Connection, key: str) -> bool:
    cur = conn.execute("DELETE FROM config WHERE key = ?", (key,))
    return cur.rowcount > 0


def get_all_config(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT key, value FROM config ORDER BY key").fetchall()
    return {r["key"]: r["value"] for r in rows}


def get_aliases(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute(
        "SELECT key, value FROM config WHERE key LIKE 'alias:%' ORDER BY key"
    ).fetchall()
    return {r["key"].removeprefix("alias:"): r["value"] for r in rows}


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

def get_messages(conn: sqlite3.Connection, category: str | None = None) -> list[dict[str, Any]]:
    if category:
        rows = conn.execute(
            "SELECT id, text, category, is_builtin FROM messages WHERE category = ? ORDER BY id",
            (category,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, text, category, is_builtin FROM messages ORDER BY category, id"
        ).fetchall()
    return [dict(r) for r in rows]


def insert_message(conn: sqlite3.Connection, text: str, category: str) -> int:
    cur = conn.execute(
        "INSERT INTO messages (text, category, is_builtin) VALUES (?, ?, 0)",
        (text, category),
    )
    return cur.lastrowid  # type: ignore[return-value]


def delete_message(conn: sqlite3.Connection, message_id: int) -> bool:
    cur = conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
    return cur.rowcount > 0


def get_random_message(conn: sqlite3.Connection, category: str) -> str | None:
    row = conn.execute(
        "SELECT text FROM messages WHERE category = ? ORDER BY RANDOM() LIMIT 1",
        (category,),
    ).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Sounds
# ---------------------------------------------------------------------------

def get_sounds(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, name, path, is_default FROM sounds ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


def insert_sound(conn: sqlite3.Connection, name: str, path: str, is_default: bool = False) -> int:
    cur = conn.execute(
        "INSERT INTO sounds (name, path, is_default) VALUES (?, ?, ?)",
        (name, path, int(is_default)),
    )
    return cur.lastrowid  # type: ignore[return-value]


def delete_sound(conn: sqlite3.Connection, sound_id: int) -> bool:
    cur = conn.execute("DELETE FROM sounds WHERE id = ?", (sound_id,))
    return cur.rowcount > 0


def get_sound_by_name(conn: sqlite3.Connection, name: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT id, name, path, is_default FROM sounds WHERE name = ?", (name,)
    ).fetchone()
    return dict(row) if row else None


def get_random_sound(conn: sqlite3.Connection) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT id, name, path, is_default FROM sounds ORDER BY RANDOM() LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


def rename_sound(conn: sqlite3.Connection, sound_id: int, new_name: str) -> bool:
    cur = conn.execute("UPDATE sounds SET name = ? WHERE id = ?", (new_name, sound_id))
    return cur.rowcount > 0
