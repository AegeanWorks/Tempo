"""Unit tests for atomic session persistence, schema refusal and quarantine."""

import json
import tempfile
import unittest
from pathlib import Path

from tempo.session import SessionState
from tempo.store import SCHEMA, SessionStore, StoreError


class SessionStoreTest(unittest.TestCase):

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.store = SessionStore(self.root / "state" / "session.json")

    def test_missing_file_reads_as_a_fresh_session(self):
        self.assertEqual(SessionState.initial(), self.store.load())

    def test_round_trip_preserves_every_field(self):
        state = SessionState(phase_index=3, running=True, started_at=12.5,
                             spent_seconds=4.25, completed_focus=2)
        self.store.save(state)
        self.assertEqual(state, self.store.load())

    def test_save_leaves_no_temporary_files_behind(self):
        self.store.save(SessionState.initial())
        leftovers = [path.name for path in self.store.path.parent.iterdir()
                     if path.name != self.store.path.name]
        self.assertEqual([], leftovers)

    def test_unknown_schema_is_refused_without_touching_the_file(self):
        self.store.path.parent.mkdir(parents=True)
        self.store.path.write_text(json.dumps({"schema": SCHEMA + 1, "session": {}}),
                                   encoding="utf-8")
        before = self.store.path.read_text(encoding="utf-8")
        with self.assertRaises(StoreError) as caught:
            self.store.load()
        self.assertIn("schema", str(caught.exception))
        self.assertEqual(before, self.store.path.read_text(encoding="utf-8"))
        self.assertFalse(self.store.quarantine.exists())

    def test_corrupt_file_is_quarantined_and_replaced_by_a_fresh_session(self):
        self.store.path.parent.mkdir(parents=True)
        self.store.path.write_text("{not json", encoding="utf-8")
        self.assertEqual(SessionState.initial(), self.store.load())
        self.assertTrue(self.store.quarantine.exists())
        self.assertFalse(self.store.path.exists())

    def test_a_blocked_quarantine_is_reported_instead_of_swallowed(self):
        self.store.path.parent.mkdir(parents=True)
        self.store.path.write_text("{not json", encoding="utf-8")
        self.store.quarantine.mkdir()
        (self.store.quarantine / "held.txt").write_text("busy", encoding="utf-8")
        with self.assertRaises(StoreError) as caught:
            self.store.load()
        self.assertIn("move the unreadable session file aside", str(caught.exception))
        self.assertTrue(self.store.path.exists())

    def test_missing_fields_count_as_corrupt(self):
        self.store.path.parent.mkdir(parents=True)
        self.store.path.write_text(json.dumps({"schema": SCHEMA, "session": {"running": True}}),
                                   encoding="utf-8")
        self.assertEqual(SessionState.initial(), self.store.load())
        self.assertTrue(self.store.quarantine.exists())


if __name__ == "__main__":
    unittest.main()
