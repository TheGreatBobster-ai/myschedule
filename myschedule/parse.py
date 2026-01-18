"""
Parsing (HTML -> structured JSON).

- Reads cached course detail HTML files from data/raw/
- Extracts course metadata
- Extracts EACH 'Termin/e' line as exactly ONE event
- Writes:
  - data/processed/courses.json
  - data/processed/events.json

Important rules (DO NOT CHANGE):
- 1 Termin-Zeile = 1 Event
- No recurrence / RRULE logic
"""

from __future__ import annotations

import json

from pathlib import Path

from datetime import datetime

from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

import argparse


# ---------------------------------------------------------------------------
# Paths (CRITICAL FIX)
# ---------------------------------------------------------------------------

# parse.py is located in: .../myschedule/myschedule/parse.py
# data folder is located in: .../myschedule/myschedule/data/
# PACKAGE_DIR always points to the folder where this file is located
PACKAGE_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_kv_table(soup: BeautifulSoup) -> Dict[str, str]:
    """
    Extracts key-value pairs from the course detail table.
    """
    # Dictionary to store extracted data
    data: Dict[str, str] = {}

    # Select the detail table by its id ending
    table = soup.select_one("table[id$='_tblDetail']")
    if not table:
        return data

    # Loop through all rows in the table
    for row in table.select("tr"):
        cells = row.find_all("td")

        # Only rows with exactly two cells are relevant
        if len(cells) != 2:
            continue

        # First cell is the key, second cell is the value
        key = cells[0].get_text(strip=True)
        value = cells[1].get_text("\n", strip=True)

        data[key] = value

    return data


# ---------------------------------------------------------------------------
# Termin parsing (CORE LOGIC)
# ---------------------------------------------------------------------------


def parse_termin_line(
    line: str,
    course_id: str,
    title: str,
) -> Optional[Dict]:
    """
    Parses exactly one 'Termin' line into exactly one event.
    """

    # Remove leading and trailing whitespace
    raw = line.strip()
    if not raw:
        return None

    # Default values for event type and note
    note: Optional[str] = None
    kind = "lecture"

    # Detect special cases like exams or block courses
    if "(Prüfung)" in raw:
        kind = "exam"
        note = "Prüfung"
        raw = raw.replace("(Prüfung)", "").strip()
    elif "Block" in raw:
        kind = "other"
        note = "Block course"

    # Split the line by commas
    parts = [p.strip() for p in raw.split(",")]

    # We expect at least 4 parts (weekday, date, time, location)
    if len(parts) < 4:
        return None

    date_str = parts[1]
    time_str = parts[2]
    location = ",".join(parts[3:]).strip()

    # Convert date to ISO format
    try:
        date_iso = datetime.strptime(date_str, "%d.%m.%Y").date().isoformat()
    except ValueError:
        return None

    # Clean up the time string
    time_str = time_str.replace("Uhr", "").strip()
    if "-" not in time_str:
        return None

    # Split start and end time
    start, end = [t.strip() for t in time_str.split("-", 1)]

    # Create a stable and unique event ID
    event_id = f"{course_id}__{date_iso}T{start.replace(':','')}"

    # Return the parsed event as dictionary
    return {
        "event_id": event_id,
        "course_id": course_id,
        "title": title,
        "kind": kind,
        "date": date_iso,
        "start": start,
        "end": end,
        "location": location,
        "note": note,
    }


# ---------------------------------------------------------------------------
# Course page parsing
# ---------------------------------------------------------------------------


def parse_course_html(
    html: str,
    source_url: str,
    course_id: str,
) -> Tuple[Dict, List[Dict]]:
    """
    Parses a single course HTML page and returns:
    - one course dictionary
    - a list of event dictionaries
    """

    # Parse the HTML page
    soup = BeautifulSoup(html, "html.parser")

    # Extract key-value information from the detail table
    kv = _extract_kv_table(soup)

    # Try to extract the course title in a robust way
    title = ""
    detail_table = soup.select_one("table[id$='_tblDetail']")
    if detail_table:
        title_el = detail_table.find_previous("h2")
        if title_el:
            title = title_el.get_text(strip=True)

    # Extract instructors if available
    instructors: List[str] = []
    if "Dozent/in" in kv:
        instructors = [
            x.strip()
            for x in kv["Dozent/in"].split(";")
            if x.strip()
        ]

    # Build the course dictionary
    course = {
        "course_id": course_id,
        "title": title,
        "semester": kv.get("Semester"),
        "type": kv.get("Veranstaltungsart"),
        "instructors": instructors,
        "department": kv.get("Durchführender Fachbereich"),
        "study_level": kv.get("Studienstufe"),
        "source_url": source_url,
    }

    # List that will contain all events for this course
    events: List[Dict] = []

    # Parse all 'Termin/e' lines
    termin_block = kv.get("Termin/e")
    if termin_block:
        for line in termin_block.splitlines():
            event = parse_termin_line(line, course_id, title)
            if event:
                events.append(event)

    return course, events


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_all(
    raw_dir: Path = PACKAGE_DIR / "data" / "raw",
    out_dir: Path = PACKAGE_DIR / "data" / "processed",
) -> None:
    """
    Parses all cached HTML files and writes the final JSON output.
    """

    # Resolve absolute paths
    raw_path = raw_dir.resolve()
    out_path = out_dir.resolve()

    # Make sure output directory exists
    out_path.mkdir(parents=True, exist_ok=True)

    print("RAW_DIR :", raw_path)
    print("FILES   :", [p.name for p in raw_path.glob("*.html")])

    courses: List[Dict] = []
    events: List[Dict] = []

    # Loop over all cached HTML files
    for html_file in sorted(raw_path.glob("*.html")):
        course_id = html_file.stem
        source_url = f"https://portal.unilu.ch/details?code={course_id}"

        # Read HTML file
        html = html_file.read_text(encoding="utf-8")

        # Parse course and events
        course, course_events = parse_course_html(
            html=html,
            source_url=source_url,
            course_id=course_id,
        )

        courses.append(course)
        events.extend(course_events)

    # Write courses JSON file
    (out_path / "courses.json").write_text(
        json.dumps(courses, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Write events JSON file
    (out_path / "events.json").write_text(
        json.dumps(events, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Local debug
# ---------------------------------------------------------------------------

# This block runs when the file is executed directly
if __name__ == "__main__":
    parse_all()
    print(f"Parsing finished. JSON written to {PACKAGE_DIR / 'data' / 'processed'}")


# ---------------------------------------------------------------------------
# CLI connection
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    # Argument parser for CLI usage
    p = argparse.ArgumentParser(
        prog="myschedule.parse",
        description="Parse cached HTML into JSON"
    )

    # Optional raw directory argument
    p.add_argument(
        "--raw-dir",
        type=Path,
        default=PACKAGE_DIR / "data" / "raw"
    )

    # Optional output directory argument
    p.add_argument(
        "--out-dir",
        type=Path,
        default=PACKAGE_DIR / "data" / "processed"
    )

    return p


def main(argv: list[str] | None = None) -> None:
    # Parse CLI arguments
    args = build_parser().parse_args(argv)

    # Run parsing with provided paths
    parse_all(
        raw_dir=args.raw_dir,
        out_dir=args.out_dir
    )

    print(f"Parsing finished. JSON written to {args.out_dir.resolve()}")


# Entry point for CLI execution
if __name__ == "__main__":
    main()
