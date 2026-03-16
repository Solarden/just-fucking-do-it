"""Sound playback using macOS built-in afplay."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BUILTIN_ASSET = Path(__file__).parent.parent / "assets" / "do_it.mp3"
USER_SOUNDS_DIR = Path.home() / ".jfdi" / "sounds"


def play_sound(sound_path: str | None = None) -> None:
    """Play a sound file non-blocking.  Falls back to built-in DO IT clip."""
    if sys.platform != "darwin":
        return

    path = Path(sound_path) if sound_path else BUILTIN_ASSET
    if not path.exists():
        return

    try:
        subprocess.Popen(
            ["afplay", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        pass


def play_do_it(custom_path: str | None = None) -> None:
    """Play the configured notification sound."""
    play_sound(custom_path)


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
