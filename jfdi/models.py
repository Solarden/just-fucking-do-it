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
class ExercisePrediction:
    """Pacing prediction for a single exercise."""

    name: str
    done: int
    goal: int
    remaining: int
    intervals_elapsed: int
    intervals_left: int
    intervals_total: int
    projected_total: int
    on_track: bool
    reps_per_set: int
    bigger_sets: int
    smaller_sets: int
    momentum: str  # "accelerating", "decelerating", "steady", or "no_data"

    @property
    def pacing_str(self) -> str:
        """Human-readable pacing plan, e.g. '5 sets of 11, 4 sets of 10'."""
        if self.intervals_left <= 0 or self.remaining <= 0:
            return ""
        parts = []
        if self.bigger_sets > 0:
            reps = self.reps_per_set + 1
            parts.append(f"{self.bigger_sets}x{reps}")
        if self.smaller_sets > 0 and self.reps_per_set > 0:
            parts.append(f"{self.smaller_sets}x{self.reps_per_set}")
        return " + ".join(parts)


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
