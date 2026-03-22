"""Sound playback using macOS built-in afplay."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BUILTIN_ASSET = Path(__file__).parent / "assets" / "do_it.mp3"
USER_SOUNDS_DIR = Path.home() / ".jfdi" / "sounds"

_current_player: subprocess.Popen | None = None


def play_sound(sound_path: str | None = None, volume: int = 100) -> None:
    """Play a sound file non-blocking.  Falls back to built-in DO IT clip.

    Kills any previously playing sound to prevent overlap.
    ``volume`` is 0-100 and maps to afplay's -v flag (0.0-1.0).
    """
    global _current_player

    if sys.platform != "darwin":
        return

    path = Path(sound_path) if sound_path else BUILTIN_ASSET
    if not path.exists():
        return

    # Stop the previous sound if still playing
    if _current_player is not None and _current_player.poll() is None:
        _current_player.terminate()

    vol = max(0.0, min(1.0, volume / 100))
    try:
        _current_player = subprocess.Popen(
            ["afplay", "-v", str(vol), str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        pass


def play_do_it(custom_path: str | None = None, volume: int = 100) -> None:
    """Play the configured notification sound."""
    play_sound(custom_path, volume=volume)


def sound_available() -> bool:
    """Check if any sound file is available to play."""
    if BUILTIN_ASSET.exists():
        return True
    return any(USER_SOUNDS_DIR.glob("*")) if USER_SOUNDS_DIR.exists() else False


def setup_sound_instructions() -> str:
    """Return instructions for setting up the DO IT sound clip."""
    return (
        "No sound clip found!\n\n"
        "To add the Shia LaBeouf 'DO IT!' sound:\n\n"
        "  Option 1 (manual):\n"
        f"    Download a clip and place it at: {BUILTIN_ASSET}\n\n"
        "  Option 2 (yt-dlp):\n"
        "    pip install yt-dlp\n"
        "    yt-dlp -x --audio-format mp3 -o 'do_it.%(ext)s' \\\n"
        "      --download-sections '*0:00-0:03' \\\n"
        "      'https://www.youtube.com/watch?v=ZXsQAXx_ao0'\n"
        f"    mv do_it.mp3 {BUILTIN_ASSET}\n\n"
        "  Option 3 (custom sound):\n"
        "    jfdi sound add mysound ~/path/to/sound.mp3\n"
        "    jfdi sound use mysound\n"
    )
