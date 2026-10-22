"""Unit tests for the phase plan, session transitions and the status read model."""

import unittest

from tempo.phases import FOCUS, LONG_BREAK, SHORT_BREAK, PhasePlan
from tempo.session import (SessionState, advanced, elapsed_seconds, paused,
                           remaining_seconds, reset, settled, started)
from tempo.status import snapshot

SHORT_PLAN = PhasePlan(focus_seconds=10, short_break_seconds=5, long_break_seconds=8,
                       cycle_length=2)


class PhasePlanTest(unittest.TestCase):

    def test_sequence_alternates_and_lengthens_every_cycle(self):
        kinds = [SHORT_PLAN.phase_at(index).kind for index in range(6)]
        self.assertEqual([FOCUS, SHORT_BREAK, FOCUS, LONG_BREAK, FOCUS, SHORT_BREAK], kinds)

    def test_negative_index_is_refused(self):
        with self.assertRaises(ValueError):
            SHORT_PLAN.phase_at(-1)

    def test_validated_names_the_bad_field(self):
        with self.assertRaisesRegex(ValueError, "focus_seconds"):
            PhasePlan(focus_seconds=0).validated()
        with self.assertRaisesRegex(ValueError, "cycle_length"):
            PhasePlan(cycle_length=0).validated()
        self.assertEqual(PhasePlan(), PhasePlan().validated())


class SessionTransitionTest(unittest.TestCase):

    def test_pause_banks_elapsed_and_resume_continues(self):
        running = started(SessionState.initial(), 100.0)
        stopped = paused(running, 104.0)
        self.assertFalse(stopped.running)
        self.assertEqual(4.0, stopped.spent_seconds)
        self.assertEqual(4.0, elapsed_seconds(stopped, 999.0))
        self.assertEqual(6.0, remaining_seconds(started(stopped, 200.0), SHORT_PLAN, 200.0))

    def test_repeated_start_and_pause_are_no_ops(self):
        running = started(SessionState.initial(), 10.0)
        self.assertIs(running, started(running, 50.0))
        stopped = paused(running, 12.0)
        self.assertIs(stopped, paused(stopped, 90.0))

    def test_advance_counts_only_finished_focus_phases(self):
        first_break = advanced(SessionState.initial(), SHORT_PLAN, 0.0)
        self.assertEqual(1, first_break.completed_focus)
        self.assertEqual(0, advanced(first_break, SHORT_PLAN, 0.0).completed_focus - 1)

    def test_paused_session_never_settles_forward(self):
        idle = SessionState.initial()
        self.assertIs(idle, settled(idle, SHORT_PLAN, 10_000.0))

    def test_settle_carries_overshoot_into_the_new_phase(self):
        running = started(SessionState.initial(), 0.0)
        landed = settled(running, SHORT_PLAN, 13.0)
        self.assertEqual(1, landed.phase_index)
        self.assertEqual(3.0, elapsed_seconds(landed, 13.0))
        self.assertEqual(1, landed.completed_focus)

    def test_reset_returns_a_fresh_session(self):
        self.assertEqual(SessionState.initial(), reset(settled(started(
            SessionState.initial(), 0.0), SHORT_PLAN, 99.0)))


class SnapshotTest(unittest.TestCase):

    def test_snapshot_reports_whole_seconds_and_cycle_position(self):
        state = settled(started(SessionState.initial(), 0.0), SHORT_PLAN, 12.0)
        payload = snapshot(state, SHORT_PLAN, 12.0)
        self.assertEqual(SHORT_BREAK, payload["phase"])
        self.assertEqual(3, payload["remaining_seconds"])
        self.assertEqual(2, payload["elapsed_seconds"])
        self.assertTrue(payload["running"])
        self.assertEqual(1, payload["completed_focus"])
        self.assertEqual(1, payload["cycle_position"])

    def test_remaining_never_goes_negative(self):
        stuck = SessionState(phase_index=0, running=False, spent_seconds=99.0)
        self.assertEqual(0, snapshot(stuck, SHORT_PLAN, 0.0)["remaining_seconds"])


if __name__ == "__main__":
    unittest.main()
