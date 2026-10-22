"""
Session state and its transitions.

A session is a frozen value: an index into the phase sequence, whether it is running,
when the current run started and how much of the phase was already spent. Every
transition returns a new state, and the clock is always passed in, so the whole model is
deterministic and testable without sleeping.

`settled` carries a state forward across phases that elapsed while nobody was watching,
which is what lets a browser poll a few times a minute without losing phases.

PRINCIPLE-003, PRINCIPLE-009, PRINCIPLE-014.
"""

from dataclasses import dataclass, replace
from typing import Optional

from tempo.phases import FOCUS, PhasePlan

MAX_SETTLE_STEPS = 512


@dataclass(frozen=True)
class SessionState:
    """Where a session stands: its phase, its run clock and its finished focus count."""

    phase_index: int = 0
    running: bool = False
    started_at: Optional[float] = None
    spent_seconds: float = 0.0
    completed_focus: int = 0

    @staticmethod
    def initial() -> "SessionState":
        """A fresh, paused session at the first focus phase."""
        return SessionState()


def elapsed_seconds(state: SessionState, now: float) -> float:
    """Seconds spent in the current phase, including the run in progress."""
    spent = state.spent_seconds
    if state.running and state.started_at is not None:
        spent += max(0.0, now - state.started_at)
    return spent


def remaining_seconds(state: SessionState, plan: PhasePlan, now: float) -> float:
    """Seconds left in the current phase, never below zero."""
    phase = plan.phase_at(state.phase_index)
    return max(0.0, phase.seconds - elapsed_seconds(state, now))


def started(state: SessionState, now: float) -> SessionState:
    """The session running from `now`; starting a running session changes nothing."""
    if state.running:
        return state
    return replace(state, running=True, started_at=now)


def paused(state: SessionState, now: float) -> SessionState:
    """The session paused, banking the elapsed run; pausing a paused one is a no-op."""
    if not state.running:
        return state
    return replace(state, running=False, started_at=None,
                   spent_seconds=elapsed_seconds(state, now))


def advanced(state: SessionState, plan: PhasePlan, now: float) -> SessionState:
    """The next phase, from a standing start, counting a finished focus phase."""
    finished_focus = plan.phase_at(state.phase_index).kind == FOCUS
    return SessionState(
        phase_index=state.phase_index + 1,
        running=state.running,
        started_at=now if state.running else None,
        spent_seconds=0.0,
        completed_focus=state.completed_focus + (1 if finished_focus else 0),
    )


def settled(state: SessionState, plan: PhasePlan, now: float) -> SessionState:
    """
    The state with every phase that ran out before `now` advanced past.

    Overshoot carries into the new phase, so a browser that polls late lands on the same
    phase it would have reached by polling every second. The step cap bounds the work a
    single long gap can ask for (PRINCIPLE-010).
    """
    current = state
    for _ in range(MAX_SETTLE_STEPS):
        if not current.running or remaining_seconds(current, plan, now) > 0:
            return current
        overshoot = elapsed_seconds(current, now) - plan.phase_at(current.phase_index).seconds
        current = advanced(current, plan, now)
        current = replace(current, started_at=now - max(0.0, overshoot))
    return current


def reset(state: SessionState) -> SessionState:
    """A fresh session, keeping nothing from the old one."""
    return SessionState.initial()
