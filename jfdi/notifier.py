"""macOS desktop notifications via osascript + sound playback."""

from __future__ import annotations

import subprocess
import sys

from jfdi import service
from jfdi.sound import play_do_it


def send_notification(title: str, message: str, sound: bool = True) -> None:
    """Send a macOS desktop notification."""
    if sys.platform != "darwin":
        return

    message_escaped = message.replace('"', '\\"')
    title_escaped = title.replace('"', '\\"')
    script = (
        f'display notification "{message_escaped}" '
        f'with title "{title_escaped}"'
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    if sound:
        cfg = service.get_config()
        if cfg.sound_enabled:
            custom = service.get_active_sound_path()
            play_do_it(custom)


def send_progress_notification(level: str = "friendly") -> None:
    """Build and send a notification based on current progress and escalation level."""
    status = service.get_status()

    if status.all_complete:
        msg = service.get_random_message("completion")
        send_notification("JFDI - ALL GOALS COMPLETE!", msg)
        return

    remaining_parts = []
    for ex in status.exercises:
        if not ex.complete:
            remaining_parts.append(f"{ex.remaining} {ex.name}")
    remaining_str = ", ".join(remaining_parts)

    if level == "shia":
        quote = service.get_random_message("nudge")
        title = "JUST FUCKING DO IT!"
        msg = f"{quote}\n\nRemaining: {remaining_str}"
    elif level == "urgent":
        quote = service.get_random_message("nudge")
        title = "JFDI - Time to move!"
        msg = f"{quote}\n\nRemaining: {remaining_str}"
    else:
        quote = service.get_random_message("quote")
        title = "JFDI - Friendly reminder"
        msg = f"Remaining: {remaining_str}\n\n\"{quote}\""

    send_notification(title, msg, sound=(level in ("urgent", "shia")))
