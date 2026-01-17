import json
import tempfile
import unittest
from pathlib import Path

from myschedule.storage import load_selected_course_ids, save_selected_course_ids


class TestStorage(unittest.TestCase):
    def test_load_missing_file_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "missing.json"
            self.assertEqual(load_selected_course_ids(p), set())

    def test_save_and_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "selected_courses.json"
            save_selected_course_ids({"fs261059", " FS261110 "}, p)
            loaded = load_selected_course_ids(p)
            self.assertEqual(loaded, {"FS261059", "FS261110"})

            data = json.loads(p.read_text(encoding="utf-8"))
            self.assertIn("selected_course_ids", data)
            self.assertEqual(sorted(data["selected_course_ids"]), ["FS261059", "FS261110"])


if __name__ == "__main__":
    unittest.main()
