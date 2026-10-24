"""Unit tests for the backend contract: status, actions and static path safety."""

import tempfile
import unittest
from pathlib import Path

from tempo.phases import FOCUS, SHORT_BREAK, PhasePlan
from tempo.server import StaticFiles, TempoApp
from tempo.store import SessionStore

SHORT_PLAN = PhasePlan(focus_seconds=10, short_break_seconds=5, long_break_seconds=8,
                       cycle_length=2)


class FakeClock:
    """A clock the test moves by hand, so no test ever sleeps (PRINCIPLE-014 R5)."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class TempoAppTest(unittest.TestCase):

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.clock = FakeClock()
        self.app = TempoApp(SessionStore(self.root / "session.json"), SHORT_PLAN, self.clock)

    def test_first_status_is_a_paused_focus_phase(self):
        status = self.app.status()
        self.assertEqual(FOCUS, status["phase"])
        self.assertFalse(status["running"])
        self.assertEqual(10, status["remaining_seconds"])

    def test_toggle_starts_then_pauses_and_the_clock_only_runs_while_started(self):
        self.assertTrue(self.app.apply("toggle")["running"])
        self.clock.now += 4
        self.assertEqual(6, self.app.status()["remaining_seconds"])
        self.assertFalse(self.app.apply("toggle")["running"])
        self.clock.now += 100
        self.assertEqual(6, self.app.status()["remaining_seconds"])

    def test_status_persists_phases_that_elapsed_between_polls(self):
        self.app.apply("toggle")
        self.clock.now += 13
        status = self.app.status()
        self.assertEqual(SHORT_BREAK, status["phase"])
        self.assertEqual(1, status["completed_focus"])
        self.assertEqual(SHORT_BREAK, self.app.status()["phase"])

    def test_skip_moves_on_and_reset_starts_over(self):
        skipped = self.app.apply("skip")
        self.assertEqual(SHORT_BREAK, skipped["phase"])
        self.assertEqual(1, skipped["completed_focus"])
        fresh = self.app.apply("reset")
        self.assertEqual(FOCUS, fresh["phase"])
        self.assertEqual(0, fresh["completed_focus"])
        self.assertFalse(fresh["running"])

    def test_configure_action_updates_plan_and_persists_it(self):
        updated = self.app.apply("configure", {
            "focus_seconds": 30 * 60,
            "short_break_seconds": 6 * 60,
            "long_break_seconds": 20 * 60,
            "cycle_length": 3
        })
        self.assertEqual(30 * 60, updated["focus_seconds"])
        self.assertEqual(6 * 60, updated["short_break_seconds"])
        self.assertEqual(20 * 60, updated["long_break_seconds"])
        self.assertEqual(3, updated["cycle_length"])
        # A fresh app instance with the same store reloads the configured plan
        reloaded_app = TempoApp(SessionStore(self.root / "session.json"), SHORT_PLAN, self.clock)
        self.assertEqual(30 * 60, reloaded_app.status()["focus_seconds"])

    def test_unknown_action_is_refused_and_leaves_the_session_alone(self):
        self.app.apply("toggle")
        with self.assertRaisesRegex(ValueError, "unknown action"):
            self.app.apply("explode")
        self.assertTrue(self.app.status()["running"])

    def test_an_invalid_plan_is_refused_when_the_app_is_built(self):
        with self.assertRaises(ValueError):
            TempoApp(SessionStore(self.root / "other.json"),
                     PhasePlan(focus_seconds=-1), self.clock)


class StaticFilesTest(unittest.TestCase):

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "web").mkdir()
        (self.root / "web" / "index.html").write_text("<p>hi</p>", encoding="utf-8")
        (self.root / "secret.txt").write_text("nope", encoding="utf-8")
        self.files = StaticFiles(self.root / "web")

    def test_root_serves_the_index(self):
        self.assertEqual("index.html", self.files.resolve("/").name)

    def test_paths_outside_the_web_root_are_refused(self):
        self.assertIsNone(self.files.resolve("/../secret.txt"))
        self.assertIsNone(self.files.resolve("/missing.css"))


if __name__ == "__main__":
    unittest.main()
