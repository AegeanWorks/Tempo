"""
The phase plan: which phase follows which, and how long each one runs.

A session alternates focus and break phases. Every `cycle_length`-th break is a long
one. The plan is a frozen value with no clock and no I/O, so a phase sequence is
reproducible from its index alone.

PRINCIPLE-009, PRINCIPLE-010.
"""

from dataclasses import dataclass

FOCUS = "focus"
SHORT_BREAK = "short-break"
LONG_BREAK = "long-break"

MIN_SECONDS = 1
MAX_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class Phase:
    """One phase of a session: its kind and its full duration in seconds."""

    kind: str
    seconds: int


@dataclass(frozen=True)
class PhasePlan:
    """Durations and cycle length for a session's phase sequence."""

    focus_seconds: int = 25 * 60
    short_break_seconds: int = 5 * 60
    long_break_seconds: int = 15 * 60
    cycle_length: int = 4

    def validated(self) -> "PhasePlan":
        """The same plan, or a ValueError naming the field that is out of range."""
        for field in ("focus_seconds", "short_break_seconds", "long_break_seconds"):
            seconds = getattr(self, field)
            if not isinstance(seconds, int) or not MIN_SECONDS <= seconds <= MAX_SECONDS:
                raise ValueError(f"{field} must be an int between {MIN_SECONDS} and {MAX_SECONDS}")
        if not isinstance(self.cycle_length, int) or self.cycle_length < 1:
            raise ValueError("cycle_length must be an int of at least 1")
        return self

    def phase_at(self, index: int) -> Phase:
        """The phase at a zero-based index: even indexes focus, odd ones break."""
        if index < 0:
            raise ValueError("phase index must not be negative")
        if index % 2 == 0:
            return Phase(FOCUS, self.focus_seconds)
        focus_done = index // 2 + 1
        if focus_done % self.cycle_length == 0:
            return Phase(LONG_BREAK, self.long_break_seconds)
        return Phase(SHORT_BREAK, self.short_break_seconds)
