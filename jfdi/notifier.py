"""macOS desktop notifications via terminal-notifier (with icon) or osascript fallback."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from jfdi import service
from jfdi.sound import play_do_it

ICON_PATH = Path(__file__).parent / "assets" / "icon.png"

_notifier_cache: str | None = None


def _get_notifier() -> str:
    """Return 'terminal-notifier' if available, else 'osascript'."""
    global _notifier_cache
    if _notifier_cache is None:
        _notifier_cache = "terminal-notifier" if shutil.which("terminal-notifier") else "osascript"
    return _notifier_cache


def send_notification(title: str, message: str, sound: bool = True) -> None:
    """Send a macOS desktop notification with icon support."""
    if sys.platform != "darwin":
        return

    notifier = _get_notifier()

    try:
        if notifier == "terminal-notifier":
            cmd = [
                "terminal-notifier",
                "-title", title,
                "-message", message,
                "-sender", "com.apple.Terminal",
            ]
            if ICON_PATH.exists():
                cmd.extend(["-appIcon", str(ICON_PATH)])
            subprocess.run(cmd, capture_output=True, timeout=5)
        else:
            script = 'display notification (item 1 of argv) with title (item 2 of argv)'
            full_script = f'on run argv\n{script}\nend run'
            subprocess.run(
                ["osascript", "-e", full_script, message, title],
                capture_output=True, timeout=5,
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    if sound:
        cfg = service.get_config()
        if cfg.sound_enabled:
            if cfg.active_sound:
                custom = service.get_active_sound_path()
            else:
                custom = service.get_random_sound_path()
            play_do_it(custom, volume=cfg.sound_volume)


_MOMENTUM_HINTS = {
    "accelerating": "You're picking up steam!",
    "decelerating": "You're slowing down -- push through!",
}


def _build_pacing_hint() -> str:
    """Build a short pacing line for notification bodies."""
    predictions = service.get_predictions()
    parts = []
    for p in predictions:
        if p.remaining <= 0 or p.on_track:
            continue
        hint = f"At this pace: {p.projected_total}/{p.goal} {p.name}."
        if p.pacing_str:
            hint += f" Do {p.pacing_str}."
        parts.append(hint)
    return " ".join(parts)


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
        pacing = _build_pacing_hint()
        msg = f"{quote}\n\nRemaining: {remaining_str}"
        if pacing:
            msg += f"\n{pacing}"
    elif level == "urgent":
        quote = service.get_random_message("nudge")
        title = "JFDI - Time to move!"
        pacing = _build_pacing_hint()
        msg = f"{quote}\n\nRemaining: {remaining_str}"
        if pacing:
            msg += f"\n{pacing}"
    else:
        quote = service.get_random_message("quote")
        title = "JFDI - Friendly reminder"
        msg = f"Remaining: {remaining_str}\n\n\"{quote}\""

    send_notification(title, msg, sound=(level in ("urgent", "shia")))
