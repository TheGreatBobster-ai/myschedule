"""
iCalendar (.ics) export.

We convert selected events into a calendar file that can be imported into:
- Google Calendar
- Outlook
- Apple Calendar
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from datetime import datetime, timezone


def _ics_escape(text: str) -> str:
    """
    Escape text for ICS fields (very small subset, sufficient for our use).
    """
    return (
        text.replace("\\", "\\\\").replace("\r\n", "\\n").replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,")
    )


def _dt_local(date_yyyy_mm_dd: str, time_hh_mm: str) -> str:
    """
    Convert date + time to ICS local datetime string 'YYYYMMDDTHHMM00'.
    """
    dt = datetime.strptime(f"{date_yyyy_mm_dd} {time_hh_mm}", "%Y-%m-%d %H:%M")
    return dt.strftime("%Y%m%dT%H%M00")


def export_events_to_ics(events: list[dict[str, Any]], out_path: str | Path) -> int:
    """
    Export events to an .ics file. Returns number of exported events.
    """
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("BEGIN:VCALENDAR")
    lines.append("VERSION:2.0")
    lines.append("PRODID:-//MySchedule//EN")
    lines.append("CALSCALE:GREGORIAN")

    count = 0
    for ev in events:
        course_id = str(ev.get("course_id", "")).strip()
        title = str(ev.get("title", "")).strip()
        date = str(ev.get("date", "")).strip()
        start = str(ev.get("start", "")).strip()
        end = str(ev.get("end", "")).strip()
        location = str(ev.get("location", "")).strip()
        note = ev.get("note", None)
        event_id = str(ev.get("event_id", "")).strip()

        if not (date and start and end):
            continue

        try:
            dtstart = _dt_local(date, start)
            dtend = _dt_local(date, end)
        except ValueError:
            continue

        summary = f"{course_id} {title}".strip() if course_id or title else "MySchedule Event"
        uid = event_id if event_id else f"{course_id}-{dtstart}"

        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{_ics_escape(uid)}")
        dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        lines.append(f"DTSTAMP:{dtstamp}")
        lines.append(f"DTSTART:{dtstart}")
        lines.append(f"DTEND:{dtend}")
        lines.append(f"SUMMARY:{_ics_escape(summary)}")
        if location:
            lines.append(f"LOCATION:{_ics_escape(location)}")
        if isinstance(note, str) and note.strip():
            lines.append(f"DESCRIPTION:{_ics_escape(note.strip())}")
        lines.append("END:VEVENT")
        count += 1

    lines.append("END:VCALENDAR")

    # ICS standard uses CRLF
    out.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    return count
