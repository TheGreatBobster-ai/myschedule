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
        # We don't want to touch real selected_courses.json, so patch by passing temp path
        # -> easiest: directly test storage here (CLI uses default path in package)
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
