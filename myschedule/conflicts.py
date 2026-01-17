"""
Conflict detection.

Given events of selected courses, detect overlaps on the same date.
Overlap rule:
    start < other_end AND end > other_start
"""

from __future__ import annotations

from typing import Any


def _time_to_minutes(hhmm: str) -> int:
    """
    Convert 'HH:MM' to minutes since midnight.
    Raises ValueError for invalid formats.
    """
    parts = hhmm.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format: {hhmm!r}")
    h = int(parts[0])
    m = int(parts[1])
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"Invalid time value: {hhmm!r}")
    return h * 60 + m


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    # Overlap definition from spec:
    # start < other_end AND end > other_start
    return a_start < b_end and a_end > b_start


def find_conflicts(events: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """
    Find overlapping event pairs (A,B), each pair appears once (i<j).
    Overlap only if same date AND time intervals overlap.
    """
    conflicts: list[tuple[dict[str, Any], dict[str, Any]]] = []

    # Pre-parse times for performance and robustness
    parsed: list[tuple[str, int, int, dict[str, Any]]] = []
    for ev in events:
        date = str(ev.get("date", "")).strip()
        start_s = str(ev.get("start", "")).strip()
        end_s = str(ev.get("end", "")).strip()
        if not date or not start_s or not end_s:
            continue
        try:
            start = _time_to_minutes(start_s)
            end = _time_to_minutes(end_s)
        except ValueError:
            continue
        # if end <= start, treat as invalid / skip (avoid weird conflicts)
        if end <= start:
            continue
        parsed.append((date, start, end, ev))

    # O(n^2) is fine for typical uni schedule sizes
    for i in range(len(parsed)):
        d1, s1, e1, ev1 = parsed[i]
        for j in range(i + 1, len(parsed)):
            d2, s2, e2, ev2 = parsed[j]
            if d1 != d2:
                continue
            if _overlaps(s1, e1, s2, e2):
                conflicts.append((ev1, ev2))

    return conflicts
