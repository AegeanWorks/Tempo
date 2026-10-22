"""
The read model the UI renders.

One function turns a settled session into the flat, JSON-safe shape the browser polls.
Keeping it apart from the transitions means the UI contract can change shape without
touching the timer's rules.

PRINCIPLE-009, PRINCIPLE-012.
"""

from typing import Dict

from tempo.phases import PhasePlan
from tempo.session import SessionState, elapsed_seconds, remaining_seconds


def snapshot(state: SessionState, plan: PhasePlan, now: float) -> Dict[str, object]:
    """A settled session as the flat payload `GET /api/status` returns."""
    phase = plan.phase_at(state.phase_index)
    remaining = remaining_seconds(state, plan, now)
    return {
        "phase": phase.kind,
        "phase_index": state.phase_index,
        "phase_seconds": phase.seconds,
        "remaining_seconds": int(round(remaining)),
        "elapsed_seconds": int(round(elapsed_seconds(state, now))),
        "running": state.running,
        "completed_focus": state.completed_focus,
        "cycle_position": state.completed_focus % plan.cycle_length,
        "cycle_length": plan.cycle_length,
    }
