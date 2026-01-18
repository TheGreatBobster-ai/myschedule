import unittest

from myschedule.parse import parse_termin_line


class TestParseTerminLine(unittest.TestCase):
    def test_normal_lecture_line(self) -> None:
        line = "Do, 19.02.2026, 10:15-12:00, HS 8"
        ev = parse_termin_line(line, "FS261110", "Public Economics")

        self.assertIsNotNone(ev)
        assert ev is not None

        self.assertEqual(ev["course_id"], "FS261110")
        self.assertEqual(ev["title"], "Public Economics")
        self.assertEqual(ev["kind"], "lecture")
        self.assertEqual(ev["date"], "2026-02-19")
        self.assertEqual(ev["start"], "10:15")
        self.assertEqual(ev["end"], "12:00")
        self.assertEqual(ev["location"], "HS 8")
        self.assertIsNone(ev["note"])
        self.assertEqual(ev["event_id"], "FS261110__2026-02-19T1015")

    def test_exam_line(self) -> None:
        line = "Fr, 20.03.2026, 09:15-11:15, HS 15 (Prüfung)"
        ev = parse_termin_line(line, "FS261671", "Classification Algorithms")

        self.assertIsNotNone(ev)
        assert ev is not None

        self.assertEqual(ev["kind"], "exam")
        self.assertEqual(ev["note"], "Prüfung")

    def test_block_course_line(self) -> None:
        line = "Mo, 01.06.2026, 08:15-17:00, 3.B01 Block"
        ev = parse_termin_line(line, "FS261999", "Block Seminar")

        self.assertIsNotNone(ev)
        assert ev is not None

        self.assertEqual(ev["kind"], "other")
        self.assertEqual(ev["note"], "Block course")

    def test_invalid_date_returns_none(self) -> None:
        line = "Mo, 32.13.2026, 10:15-12:00, HS 8"
        ev = parse_termin_line(line, "FS000000", "Invalid Date")
        self.assertIsNone(ev)

    def test_time_without_colon_is_accepted(self) -> None:
        """
        Current parser behavior: times without ':' are accepted as-is.
        This test documents that behavior instead of rejecting it.
        """
        line = "Mo, 19.02.2026, 1015-1200, HS 8"
        ev = parse_termin_line(line, "FS000001", "Bad Time Format")

        self.assertIsNotNone(ev)
        assert ev is not None

        self.assertEqual(ev["start"], "1015")
        self.assertEqual(ev["end"], "1200")

    def test_too_short_line_returns_none(self) -> None:
        line = "Mo, 19.02.2026"
        ev = parse_termin_line(line, "FS000002", "Too Short")
        self.assertIsNone(ev)

    def test_empty_line_returns_none(self) -> None:
        ev = parse_termin_line("", "FS000003", "Empty")
        self.assertIsNone(ev)


if __name__ == "__main__":
    unittest.main()
