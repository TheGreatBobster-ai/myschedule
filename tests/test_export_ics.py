import tempfile
import unittest
from pathlib import Path

from myschedule.export_ics import export_events_to_ics


class TestExportICS(unittest.TestCase):
    def test_export_creates_file_and_contains_calendar(self) -> None:
        events = [
            {
                "event_id": "FS261110__2026-02-19T1015",
                "course_id": "FS261110",
                "title": "Public Economics",
                "date": "2026-02-19",
                "start": "10:15",
                "end": "12:00",
                "location": "HS 8",
                "note": None,
            }
        ]

        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out.ics"
            n = export_events_to_ics(events, out)
            self.assertEqual(n, 1)
            text = out.read_text(encoding="utf-8")
            self.assertIn("BEGIN:VCALENDAR", text)
            self.assertIn("BEGIN:VEVENT", text)
            self.assertIn("SUMMARY:FS261110 Public Economics", text)


if __name__ == "__main__":
    unittest.main()
