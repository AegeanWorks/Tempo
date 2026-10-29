"""Unit tests for the UI inventory parser: the handler list is the guard's evidence."""

import tempfile
import unittest
from pathlib import Path

from tools.ui_inventory import handler_entries


class HandlerEntriesTest(unittest.TestCase):

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def test_quoted_and_hyphenated_keys_are_included(self):
        script = self.root / "app.js"
        script.write_text(
            'var ACTIONS = {\n'
            '  toggle: "toggle",\n'
            '  "save-settings": "save-settings",\n'
            '  "close-settings": "close-settings"\n'
            '};\n', encoding="utf-8")
        self.assertEqual(
            {"handler toggle", "handler save-settings", "handler close-settings"},
            handler_entries(script))


if __name__ == "__main__":
    unittest.main()
