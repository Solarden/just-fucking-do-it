"""Background notification daemon.

Forks a process that sends periodic notifications based on
escalation level and quiet hours.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from datetime import datetime

from jfdi import service
from jfdi.notifier import send_progress_notification


def _daemon_loop() -> None:
    """Main daemon loop -- runs until killed."""
    while True:
        try:
            cfg = service.get_config()
            interval_seconds = cfg.interval_minutes * 60

            if service.is_quiet_time():
                time.sleep(interval_seconds)
                continue

            status = service.get_status()

            if status.all_complete:
                send_progress_notification("friendly")
                _sleep_until_tomorrow()
                continue

            level = service.get_escalation_level()
            send_progress_notification(level)
            time.sleep(interval_seconds)

        except KeyboardInterrupt:
            break
        except Exception:
            time.sleep(60)


def _sleep_until_tomorrow() -> None:
    """Sleep until midnight + 1 minute to start a new day."""
    now = datetime.now()
    tomorrow = now.replace(hour=0, minute=1, second=0, microsecond=0)
    if tomorrow <= now:
        tomorrow = tomorrow.replace(day=now.day + 1)
    sleep_seconds = (tomorrow - now).total_seconds()
    time.sleep(max(60, sleep_seconds))


def start_daemon() -> int | None:
    """Fork a background daemon.  Returns the child PID, or None if already running."""
    if service.is_daemon_running():
        return service.get_daemon_pid()

    pid = os.fork()
    if pid > 0:
        # Parent: record the child PID and return
        service.save_daemon_pid(pid)
        return pid

    # Child: detach and run the loop
    os.setsid()
    # Close standard file descriptors
    sys.stdin.close()
    devnull = os.open(os.devnull, os.O_RDWR)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)

    service.save_daemon_pid(os.getpid())

    try:
        _daemon_loop()
    finally:
        service.clear_daemon_pid()
        os._exit(0)


def stop_daemon() -> bool:
    """Stop the running daemon.  Returns True if stopped, False if wasn't running."""
    pid = service.get_daemon_pid()
    if pid is None:
        return False

    if not service.is_daemon_running():
        service.clear_daemon_pid()
        return False

    try:
        os.kill(pid, signal.SIGTERM)
        # Give it a moment to clean up
        for _ in range(10):
            try:
                os.kill(pid, 0)
                time.sleep(0.1)
            except ProcessLookupError:
                break
    except ProcessLookupError:
        pass

    service.clear_daemon_pid()
    return True


def daemon_status() -> dict[str, str | int | bool | None]:
    """Return daemon status info."""
    running = service.is_daemon_running()
    pid = service.get_daemon_pid() if running else None

    started_at = None
    if running:
        service._ensure_db()
        from jfdi import db
        with db.get_conn() as conn:
            started_at = db.get_config_value(conn, "daemon_started_at")

    return {
        "running": running,
        "pid": pid,
        "started_at": started_at,
    }
