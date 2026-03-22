"""Business logic layer.

All functions return model dataclasses.  The CLI and daemon call these
functions -- they never touch db.py directly.
"""

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import signal
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from jfdi import db
from jfdi.db import Database
from jfdi.models import (
    AppConfig,
    DailyStatus,
    DayRecord,
    ExerciseProgress,
    ExercisePrediction,
    MessageEntry,
    SoundEntry,
    StreakInfo,
)

SOUNDS_DIR = Path.home() / ".jfdi" / "sounds"
EXPORTS_DIR = Path.home() / ".jfdi" / "exports"

_db: Database | None = None


def set_database(database: Database | None) -> None:
    """Inject a Database instance (used for testing)."""
    global _db
    _db = database


def _ensure_db() -> Database:
    """Return the active Database, initialising it if needed."""
    global _db
    if _db is None:
        _db = db._default
    _db.init_db()
    return _db


# ---------------------------------------------------------------------------
# Core tracking
# ---------------------------------------------------------------------------


def log_set(exercise: str, reps: int) -> ExerciseProgress:
    """Log a set of reps.  Accepts exercise name or alias."""
    if reps <= 0:
        raise ValueError("Reps must be a positive number.")
    database = _ensure_db()
    exercise = resolve_alias(exercise)
    with database.get_conn() as conn:
        ex = db.get_exercise_by_name(conn, exercise)
        if not ex:
            raise ValueError(f"Unknown exercise: '{exercise}'. Use 'jfdi config add' to create it.")
        if not ex["active"]:
            raise ValueError(f"Exercise '{exercise}' is inactive. Re-add it with 'jfdi config add'.")
        db.insert_log(conn, ex["id"], reps)
        total = db.get_today_total(conn, ex["id"])
        sets = [r["reps"] for r in db.get_today_logs(conn, ex["id"])]
    return ExerciseProgress(name=exercise, done=total, goal=ex["daily_goal"], sets=sets)


def undo_last() -> str:
    """Undo the most recent log entry.  Returns description of what was undone."""
    database = _ensure_db()
    with database.get_conn() as conn:
        deleted = db.delete_last_log(conn)
    if not deleted:
        return "Nothing to undo."
    return f"Undone: {deleted['reps']} {deleted['name']}"


def get_status() -> DailyStatus:
    database = _ensure_db()
    today = datetime.now().strftime("%Y-%m-%d")
    exercises: list[ExerciseProgress] = []
    with database.get_conn() as conn:
        for ex in db.get_active_exercises(conn):
            total = db.get_today_total(conn, ex["id"])
            sets = [r["reps"] for r in db.get_today_logs(conn, ex["id"])]
            exercises.append(
                ExerciseProgress(name=ex["name"], done=total, goal=ex["daily_goal"], sets=sets)
            )
        daemon_running = is_daemon_running()
        pid_str = db.get_config_value(conn, "daemon_pid")
        daemon_pid = int(pid_str) if pid_str else None

    all_complete = all(e.complete for e in exercises) and len(exercises) > 0
    return DailyStatus(
        date=today,
        exercises=exercises,
        all_complete=all_complete,
        daemon_running=daemon_running,
        daemon_pid=daemon_pid if daemon_running else None,
    )


def get_history(days: int = 7) -> list[DayRecord]:
    database = _ensure_db()
    with database.get_conn() as conn:
        rows = db.get_daily_totals(conn, days)
        active = {e["name"]: e["daily_goal"] for e in db.get_active_exercises(conn)}

    by_day: dict[str, dict[str, int]] = defaultdict(dict)
    goals_by_day: dict[str, dict[str, int]] = defaultdict(dict)
    for r in rows:
        by_day[r["day"]][r["name"]] = r["total"]
        goals_by_day[r["day"]][r["name"]] = r["daily_goal"]

    records = []
    for day in sorted(by_day.keys(), reverse=True):
        ex = by_day[day]
        goals = goals_by_day[day]
        complete = all(ex.get(name, 0) >= goal for name, goal in goals.items())
        records.append(DayRecord(date=day, exercises=ex, complete=complete))
    return records


def get_streak() -> StreakInfo:
    _ensure_db()  # init only — no conn needed here
    history = get_history(days=365)
    today_str = datetime.now().strftime("%Y-%m-%d")

    completed_today = False
    if history and history[0].date == today_str:
        completed_today = history[0].complete

    # Current streak: count consecutive complete days from the most recent day.
    # If today exists but is incomplete, skip it (day isn't over yet) and
    # start counting from yesterday.
    current = 0
    for record in history:
        if record.date == today_str:
            if record.complete:
                current += 1
            continue
        if record.complete:
            current += 1
        else:
            break

    # Best streak: scan all records for the longest run of complete days.
    best = 0
    streak = 0
    for record in history:
        if record.complete:
            streak += 1
        else:
            best = max(best, streak)
            streak = 0
    best = max(best, streak)

    return StreakInfo(current=current, best=best, completed_today=completed_today)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def get_config() -> AppConfig:
    database = _ensure_db()
    with database.get_conn() as conn:
        all_cfg = db.get_all_config(conn)
        exercises_raw = db.get_active_exercises(conn)
        aliases = db.get_aliases(conn)

    exercises = {e["name"]: e["daily_goal"] for e in exercises_raw}
    return AppConfig(
        interval_minutes=int(all_cfg.get("interval", "30")),
        sound_enabled=all_cfg.get("sound_enabled", "1") == "1",
        exercises=exercises,
        aliases=aliases,
        sound_volume=int(all_cfg.get("sound_volume", "100")),
        active_sound=all_cfg.get("active_sound"),
        quiet_hours_start=int(all_cfg.get("quiet_hours_start", "8")),
        quiet_hours_end=int(all_cfg.get("quiet_hours_end", "22")),
    )


def set_interval(minutes: int) -> None:
    if minutes < 1:
        raise ValueError("Interval must be at least 1 minute.")
    database = _ensure_db()
    with database.get_conn() as conn:
        db.set_config_value(conn, "interval", str(minutes))


def set_sound(enabled: bool) -> None:
    database = _ensure_db()
    with database.get_conn() as conn:
        db.set_config_value(conn, "sound_enabled", "1" if enabled else "0")


def set_volume(level: int) -> None:
    if not (0 <= level <= 100):
        raise ValueError("Volume must be between 0 and 100.")
    database = _ensure_db()
    with database.get_conn() as conn:
        db.set_config_value(conn, "sound_volume", str(level))


def set_quiet_hours(start: int, end: int) -> None:
    if not (0 <= start <= 23 and 0 <= end <= 23):
        raise ValueError("Hours must be between 0 and 23.")
    database = _ensure_db()
    with database.get_conn() as conn:
        db.set_config_value(conn, "quiet_hours_start", str(start))
        db.set_config_value(conn, "quiet_hours_end", str(end))


def is_quiet_time() -> bool:
    cfg = get_config()
    hour = datetime.now().hour
    start, end = cfg.quiet_hours_start, cfg.quiet_hours_end
    if start <= end:
        return not (start <= hour < end)
    # Wraps midnight (e.g. 22-6)
    return not (hour >= start or hour < end)


def add_exercise(name: str, goal: int) -> None:
    if goal < 1:
        raise ValueError("Goal must be at least 1.")
    name = name.lower().strip()
    database = _ensure_db()
    with database.get_conn() as conn:
        db.add_exercise(conn, name, goal)


def remove_exercise(name: str) -> None:
    name = name.lower().strip()
    database = _ensure_db()
    with database.get_conn() as conn:
        if not db.deactivate_exercise(conn, name):
            raise ValueError(f"No active exercise named '{name}'.")


# ---------------------------------------------------------------------------
# Aliases
# ---------------------------------------------------------------------------


def set_alias(exercise: str, alias: str) -> None:
    exercise = exercise.lower().strip()
    alias = alias.lower().strip()
    database = _ensure_db()
    with database.get_conn() as conn:
        ex = db.get_exercise_by_name(conn, exercise)
        if not ex:
            raise ValueError(f"Unknown exercise: '{exercise}'.")
        db.set_config_value(conn, f"alias:{alias}", exercise)


def resolve_alias(alias_or_name: str) -> str:
    """Resolve an alias to an exercise name.  Returns input unchanged if not an alias."""
    alias_or_name = alias_or_name.lower().strip()
    database = _ensure_db()
    with database.get_conn() as conn:
        val = db.get_config_value(conn, f"alias:{alias_or_name}")
    return val if val else alias_or_name


def remove_alias(alias: str) -> None:
    alias = alias.lower().strip()
    database = _ensure_db()
    with database.get_conn() as conn:
        if not db.delete_config_key(conn, f"alias:{alias}"):
            raise ValueError(f"No alias '{alias}' found.")


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


def list_messages(category: str | None = None) -> list[MessageEntry]:
    database = _ensure_db()
    with database.get_conn() as conn:
        rows = db.get_messages(conn, category)
    return [
        MessageEntry(id=r["id"], text=r["text"], category=r["category"], is_builtin=bool(r["is_builtin"]))
        for r in rows
    ]


def add_message(text: str, category: str) -> MessageEntry:
    category = category.lower().strip()
    if category not in ("nudge", "completion", "quote"):
        raise ValueError("Category must be 'nudge', 'completion', or 'quote'.")
    database = _ensure_db()
    with database.get_conn() as conn:
        msg_id = db.insert_message(conn, text, category)
    return MessageEntry(id=msg_id, text=text, category=category, is_builtin=False)


def remove_message(message_id: int) -> None:
    database = _ensure_db()
    with database.get_conn() as conn:
        if not db.delete_message(conn, message_id):
            raise ValueError(f"No message with ID {message_id}.")


def get_random_message(category: str) -> str:
    database = _ensure_db()
    with database.get_conn() as conn:
        msg = db.get_random_message(conn, category)
    return msg or "DO IT!"


# ---------------------------------------------------------------------------
# Sounds
# ---------------------------------------------------------------------------


def list_sounds() -> list[SoundEntry]:
    database = _ensure_db()
    with database.get_conn() as conn:
        rows = db.get_sounds(conn)
    return [
        SoundEntry(id=r["id"], name=r["name"], path=r["path"], is_default=bool(r["is_default"]))
        for r in rows
    ]


def add_sound(name: str, file_path: str) -> SoundEntry:
    name = name.lower().strip()
    # Strip file extensions from the name so users don't end up with "arnold.mp3" as a name
    for ext in (".mp3", ".wav", ".m4a", ".aiff"):
        if name.endswith(ext):
            name = name[: -len(ext)]
    src = Path(file_path).expanduser().resolve()
    if not src.exists():
        raise ValueError(f"File not found: {src}")
    if src.suffix.lower() not in (".mp3", ".wav", ".m4a", ".aiff"):
        raise ValueError("Unsupported audio format. Use mp3, wav, m4a, or aiff.")

    SOUNDS_DIR.mkdir(parents=True, exist_ok=True)
    dest = SOUNDS_DIR / f"{name}{src.suffix}"
    shutil.copy2(str(src), str(dest))

    database = _ensure_db()
    with database.get_conn() as conn:
        sound_id = db.insert_sound(conn, name, str(dest))
    return SoundEntry(id=sound_id, name=name, path=str(dest), is_default=False)


def remove_sound(sound_id: int) -> None:
    database = _ensure_db()
    with database.get_conn() as conn:
        if not db.delete_sound(conn, sound_id):
            raise ValueError(f"No sound with ID {sound_id}.")


def set_active_sound(name: str) -> None:
    name = name.lower().strip()
    database = _ensure_db()
    with database.get_conn() as conn:
        sound = db.get_sound_by_name(conn, name)
        if not sound:
            raise ValueError(f"No sound named '{name}'. Use 'jfdi sound list' to see available sounds.")
        db.set_config_value(conn, "active_sound", name)


def get_active_sound_path() -> str | None:
    """Returns the path to the currently active sound file, or None for default."""
    database = _ensure_db()
    with database.get_conn() as conn:
        name = db.get_config_value(conn, "active_sound")
        if not name:
            return None
        sound = db.get_sound_by_name(conn, name)
    return sound["path"] if sound else None


def get_random_sound_path() -> str | None:
    """Returns path to a random sound from the library, or None if empty."""
    database = _ensure_db()
    with database.get_conn() as conn:
        sound = db.get_random_sound(conn)
    return sound["path"] if sound else None


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def _unique_export_path(directory: Path, stem: str, ext: str) -> Path:
    """Return a path that doesn't collide with existing files, appending _2, _3, etc."""
    candidate = directory / f"{stem}{ext}"
    if not candidate.exists():
        return candidate
    counter = 2
    while True:
        candidate = directory / f"{stem}_{counter}{ext}"
        if not candidate.exists():
            return candidate
        counter += 1


def export_history(fmt: str = "csv", days: int | None = None) -> str:
    database = _ensure_db()
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    with database.get_conn() as conn:
        rows = db.get_all_logs_for_export(conn, days)

    stem = f"jfdi_export_{today}"
    if fmt == "json":
        out_path = _unique_export_path(EXPORTS_DIR, stem, ".json")
        with open(out_path, "w") as f:
            json.dump(rows, f, indent=2, default=str)
    else:
        out_path = _unique_export_path(EXPORTS_DIR, stem, ".csv")
        with open(out_path, "w", newline="") as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

    return str(out_path)


# ---------------------------------------------------------------------------
# Daemon management
# ---------------------------------------------------------------------------


def save_daemon_pid(pid: int) -> None:
    database = _ensure_db()
    with database.get_conn() as conn:
        db.set_config_value(conn, "daemon_pid", str(pid))
        db.set_config_value(conn, "daemon_started_at", datetime.now().isoformat())


def clear_daemon_pid() -> None:
    database = _ensure_db()
    with database.get_conn() as conn:
        db.delete_config_key(conn, "daemon_pid")
        db.delete_config_key(conn, "daemon_started_at")


def get_daemon_pid() -> int | None:
    database = _ensure_db()
    with database.get_conn() as conn:
        val = db.get_config_value(conn, "daemon_pid")
    return int(val) if val else None


def get_daemon_started_at() -> str | None:
    database = _ensure_db()
    with database.get_conn() as conn:
        return db.get_config_value(conn, "daemon_started_at")


def is_daemon_running() -> bool:
    pid = get_daemon_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        clear_daemon_pid()
        return False


def _time_pct_today() -> float:
    """Fraction of the active window elapsed (minute-level precision)."""
    cfg = get_config()
    now = datetime.now()
    start_min = cfg.quiet_hours_start * 60
    end_min = cfg.quiet_hours_end * 60
    now_min = now.hour * 60 + now.minute
    total = end_min - start_min
    if total <= 0:
        total = 24 * 60
    elapsed = max(0, now_min - start_min)
    return min(1.0, elapsed / total) if total > 0 else 1.0


def get_escalation_level() -> str:
    """Returns 'friendly', 'urgent', or 'shia' based on progress vs time of day."""
    status = get_status()

    if not status.exercises:
        return "friendly"
    if status.all_complete:
        return "friendly"

    total_done = sum(e.done for e in status.exercises)
    total_goal = sum(e.goal for e in status.exercises)
    progress_pct = total_done / total_goal if total_goal > 0 else 1.0
    time_pct = _time_pct_today()

    if progress_pct >= time_pct:
        return "friendly"
    elif progress_pct >= time_pct * 0.5:
        return "urgent"
    else:
        return "shia"


# ---------------------------------------------------------------------------
# Prediction & pacing
# ---------------------------------------------------------------------------


def _compute_momentum(sets: list[int]) -> str:
    """Compare first half vs second half of sets to detect trend."""
    if len(sets) < 4:
        return "no_data"
    mid = len(sets) // 2
    first_avg = sum(sets[:mid]) / mid
    second_avg = sum(sets[mid:]) / (len(sets) - mid)
    if first_avg == 0:
        return "accelerating" if second_avg > 0 else "no_data"
    ratio = second_avg / first_avg
    if ratio > 1.1:
        return "accelerating"
    elif ratio < 0.9:
        return "decelerating"
    return "steady"


def get_predictions() -> list[ExercisePrediction]:
    """Compute pacing predictions for every active exercise."""
    cfg = get_config()
    status = get_status()
    now = datetime.now()

    start_min = cfg.quiet_hours_start * 60
    end_min = cfg.quiet_hours_end * 60
    now_min = now.hour * 60 + now.minute
    total_active_min = end_min - start_min
    if total_active_min <= 0:
        total_active_min = 24 * 60

    intervals_total = max(1, total_active_min // cfg.interval_minutes)
    elapsed_min = max(0, now_min - start_min)
    intervals_elapsed = max(1, elapsed_min // cfg.interval_minutes) if elapsed_min > 0 else 0
    intervals_left = max(0, intervals_total - intervals_elapsed)

    predictions: list[ExercisePrediction] = []
    for ex in status.exercises:
        if ex.complete:
            predictions.append(ExercisePrediction(
                name=ex.name, done=ex.done, goal=ex.goal, remaining=0,
                intervals_elapsed=intervals_elapsed, intervals_left=intervals_left,
                intervals_total=intervals_total, projected_total=ex.done,
                on_track=True, reps_per_set=0, bigger_sets=0, smaller_sets=0,
                momentum=_compute_momentum(ex.sets),
            ))
            continue

        if intervals_elapsed > 0:
            pace = ex.done / intervals_elapsed
            projected = round(pace * intervals_total)
        else:
            projected = 0

        remaining = ex.remaining
        if intervals_left > 0:
            base, extra = divmod(remaining, intervals_left)
        else:
            base, extra = remaining, 0

        predictions.append(ExercisePrediction(
            name=ex.name,
            done=ex.done,
            goal=ex.goal,
            remaining=remaining,
            intervals_elapsed=intervals_elapsed,
            intervals_left=intervals_left,
            intervals_total=intervals_total,
            projected_total=projected,
            on_track=projected >= ex.goal,
            reps_per_set=base,
            bigger_sets=extra,
            smaller_sets=max(0, intervals_left - extra),
            momentum=_compute_momentum(ex.sets),
        ))

    return predictions


def get_adaptive_interval() -> int:
    """Return an adjusted notification interval (minutes) based on pacing.

    Behind pace  -> halve the interval (floor 5 min)
    On pace      -> use configured interval
    Ahead of pace -> 1.5x the interval (cap at 2x configured)
    """
    cfg = get_config()
    status = get_status()
    base = cfg.interval_minutes

    if not status.exercises or status.all_complete:
        return base

    total_done = sum(e.done for e in status.exercises)
    total_goal = sum(e.goal for e in status.exercises)
    progress_pct = total_done / total_goal if total_goal > 0 else 1.0
    time_pct = _time_pct_today()

    if time_pct == 0:
        return base

    ratio = progress_pct / time_pct

    if ratio >= 1.0:
        return int(base * 1.5)
    elif ratio >= 0.5:
        return base
    else:
        return max(5, base // 2)
