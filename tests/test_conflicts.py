"""
Unit tests for conflict detection.

Definition used here:
- A conflict exists if two events overlap in time on the same date.
- Touching endpoints (end == start) is NOT a conflict.
"""

import unittest

from myschedule.conflicts import find_conflicts


class TestConflicts(unittest.TestCase):
    def test_overlap_same_day(self) -> None:
        events = [
            {"date": "2026-02-19", "start": "10:00", "end": "11:00", "course_id": "A", "title": "A"},
            {"date": "2026-02-19", "start": "10:30", "end": "12:00", "course_id": "B", "title": "B"},
        ]
        confs = find_conflicts(events)
        self.assertEqual(len(confs), 1)

    def test_no_overlap_touching_end(self) -> None:
        # end == start is allowed (no overlap)
        events = [
            {"date": "2026-02-19", "start": "10:00", "end": "11:00"},
            {"date": "2026-02-19", "start": "11:00", "end": "12:00"},
        ]
        confs = find_conflicts(events)
        self.assertEqual(len(confs), 0)

    def test_different_day_no_conflict(self) -> None:
        events = [
            {"date": "2026-02-19", "start": "10:00", "end": "11:00"},
            {"date": "2026-02-20", "start": "10:30", "end": "12:00"},
        ]
        confs = find_conflicts(events)
        self.assertEqual(len(confs), 0)


if __name__ == "__main__":
    unittest.main()
