"""Pure data models -- the API contract between layers.

These dataclasses have ZERO imports from other jfdi modules.
Any frontend (CLI, GUI, web) consumes these same objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExerciseProgress:
    """Progress for a single exercise today."""

    name: str
    done: int
    goal: int
    sets: list[int] = field(default_factory=list)

    @property
    def remaining(self) -> int:
        return max(0, self.goal - self.done)

    @property
    def complete(self) -> bool:
        return self.done >= self.goal

    @property
    def pct(self) -> float:
        return min(100.0, (self.done / self.goal * 100)) if self.goal > 0 else 100.0


@dataclass
class DailyStatus:
    """Full status snapshot for a single day."""

    date: str
    exercises: list[ExerciseProgress]
    all_complete: bool
    daemon_running: bool = False
    daemon_pid: int | None = None


@dataclass
class StreakInfo:
    current: int
    best: int
    completed_today: bool


@dataclass
class DayRecord:
    """Historical record for one day."""

    date: str
    exercises: dict[str, int] = field(default_factory=dict)
    complete: bool = False


@dataclass
class AppConfig:
    interval_minutes: int = 30
    sound_enabled: bool = True
    exercises: dict[str, int] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)
    active_sound: str | None = None
    quiet_hours_start: int = 8
    quiet_hours_end: int = 22


@dataclass
class MessageEntry:
    id: int
    text: str
    category: str  # "nudge", "completion", or "quote"
    is_builtin: bool = False


@dataclass
class SoundEntry:
    id: int
    name: str
    path: str
    is_default: bool = False
