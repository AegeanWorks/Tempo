"""
The read model the UI renders.

One function turns a settled session into the flat, JSON-safe shape the browser polls.
Keeping it apart from the transitions means the UI contract can change shape without
touching the timer's rules.

PRINCIPLE-009, PRINCIPLE-012.
"""

from datetime import datetime
from typing import Dict

from tempo.phases import PhasePlan
from tempo.session import SessionState, elapsed_seconds, remaining_seconds


def snapshot(state: SessionState, plan: PhasePlan, now: float) -> Dict[str, object]:
    """A settled session as the flat payload `GET /api/status` returns."""
    phase = plan.phase_at(state.phase_index)
    remaining = remaining_seconds(state, plan, now)
    try:
        today = datetime.fromtimestamp(now).date()
        today_count = 0
        today_seconds = 0
        for timestamp, seconds in state.history:
            if datetime.fromtimestamp(timestamp).date() == today:
                today_count += 1
                today_seconds += plan.focus_seconds if seconds is None else seconds
    except (OSError, OverflowError, ValueError):
        today_count = state.completed_focus
        today_seconds = state.completed_focus * plan.focus_seconds
    if state.history:
        total_seconds = sum(plan.focus_seconds if seconds is None else seconds
                            for _, seconds in state.history)
    else:
        total_seconds = state.completed_focus * plan.focus_seconds
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
        "focus_seconds": plan.focus_seconds,
        "short_break_seconds": plan.short_break_seconds,
        "long_break_seconds": plan.long_break_seconds,
        "today_focus_count": today_count,
        "today_focus_seconds": today_seconds,
        "total_focus_seconds": total_seconds,
    }
