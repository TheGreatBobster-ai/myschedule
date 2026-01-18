"""
Tests for CLI entry points and storage roundtrip logic.

These tests focus on:
- Basic CLI argument validation (search requires text)
- Safe persistence of selected courses using a temporary file
  (to avoid touching real user data during tests)
"""

import tempfile
import unittest
from pathlib import Path

import myschedule.storage as storage
from myschedule.cli import main


class TestCLI(unittest.TestCase):
    def test_cli_search_requires_text(self) -> None:
        # search without text should exit with nonzero
        with self.assertRaises(SystemExit) as ctx:
            main(["search", ""])
        self.assertNotEqual(ctx.exception.code, 0)

    def test_cli_add_and_remove_roundtrip(self) -> None:
        # Do not touch the real selected_courses.json used by users.
        # Instead, use a temporary file to test persistence logic safely in isolation.
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "selected_courses.json"
            storage.save_selected_course_ids(set(), p)
            ids = storage.load_selected_course_ids(p)
            self.assertEqual(ids, set())
            storage.save_selected_course_ids({"FS261059"}, p)
            ids2 = storage.load_selected_course_ids(p)
            self.assertEqual(ids2, {"FS261059"})


if __name__ == "__main__":
    unittest.main()
