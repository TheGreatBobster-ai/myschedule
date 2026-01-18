"""
CLI (Command Line Interface).

This module provides quick terminal commands for power users and for testing, e.g.:

    myschedule search <text>
    myschedule add <course_id>
    myschedule remove <course_id>
    myschedule conflicts
    myschedule export <file.ics>
    myschedule interactive

Note:
- The interactive UI lives in myschedule/interactive.py
- This CLI is intentionally simple and prints plain text (no rich formatting)
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from myschedule.conflicts import find_conflicts
from myschedule.export_ics import export_events_to_ics
from myschedule.storage import load_selected_course_ids, save_selected_course_ids


def _processed_dir() -> Path:
    """
    Return the directory that contains processed JSON data (courses/events).
    """
    base_dir = Path(__file__).resolve().parent
    return base_dir / "data" / "processed"


def _load_json(path: Path) -> Any:
    """
    Load JSON from a file.

    CLI behavior: never crash if data is missing or broken.
    Instead, return [] as a safe default so commands can still run.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return []


def _build_indexes() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """
    Load courses/events once and create in-memory indexes:
    - courses list
    - course_by_id dict
    - events_by_course_id dict
    => Avoids repeatedly scanning large lists for every command.
    """
    processed = _processed_dir()
    courses_path = processed / "courses.json"
    events_path = processed / "events.json"

    courses_raw = _load_json(courses_path)
    events_raw = _load_json(events_path)

    courses: list[dict[str, Any]] = list(courses_raw) if isinstance(courses_raw, list) else []
    events: list[dict[str, Any]] = list(events_raw) if isinstance(events_raw, list) else []

    course_by_id: dict[str, dict[str, Any]] = {}
    for c in courses:
        cid = str(c.get("course_id", "")).strip().upper()
        if cid:
            course_by_id[cid] = c

    events_by_course_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in events:
        cid = str(e.get("course_id", "")).strip().upper()
        if cid:
            events_by_course_id[cid].append(e)

    return courses, course_by_id, events_by_course_id


def _cmd_search(args: argparse.Namespace, courses: list[dict[str, Any]]) -> int:
    """
    Search courses by substring match in course_id, title, or instructor names.
    """
    query = (args.text or "").strip().lower()
    if not query:
        print("Please provide a search text.")
        return 1

    matches: list[tuple[str, str]] = []
    for c in courses:
        cid = str(c.get("course_id", "")).strip().upper()
        title = str(c.get("title", "") or "").strip()
        instructors = c.get("instructors", [])
        instr_text = (
            " ".join([str(x) for x in instructors]) if isinstance(instructors, list) else str(instructors or "")
        )

        hay = f"{cid} {title} {instr_text}".lower()
        if query in hay:
            pretty_title = title if title else "(no title)"
            matches.append((cid, pretty_title))

    if not matches:
        print("No results.")
        return 0

    # show max 20
    for cid, title in matches[:20]:
        print(f"{cid} | {title}")
    if len(matches) > 20:
        print(f"... and {len(matches) - 20} more results")

    return 0


def _cmd_add(args: argparse.Namespace, course_by_id: dict[str, dict[str, Any]]) -> int:
    """
    Add a course_id to the persistent selection (selected_courses.json).
    """
    cid = (args.course_id or "").strip().upper()
    if not cid:
        print("Please provide a course_id.")
        return 1

    # optional validation: allow adding unknown, but warn
    if cid not in course_by_id:
        print(f"Warning: course_id '{cid}' not found in courses.json (adding anyway).")

    selected = load_selected_course_ids()
    if cid in selected:
        print(f"Already selected: {cid}")
        return 0

    selected.add(cid)
    save_selected_course_ids(selected)
    print(f"Added: {cid} (selected: {len(selected)})")
    return 0


def _cmd_remove(args: argparse.Namespace) -> int:
    """
    Remove a course_id from the persistent selection (selected_courses.json).
    """
    cid = (args.course_id or "").strip().upper()
    if not cid:
        print("Please provide a course_id.")
        return 1

    selected = load_selected_course_ids()
    if cid not in selected:
        print(f"Not selected: {cid}")
        return 0

    selected.remove(cid)
    save_selected_course_ids(selected)
    print(f"Removed: {cid} (selected: {len(selected)})")
    return 0


def _selected_events(
    selected_ids: set[str], events_by_course_id: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    """
    Collect all event dicts for the currently selected courses.
    """
    out: list[dict[str, Any]] = []
    for cid in sorted(selected_ids):
        out.extend(events_by_course_id.get(cid, []))
    return out


def _cmd_conflicts(args: argparse.Namespace, events_by_course_id: dict[str, list[dict[str, Any]]]) -> int:
    """
    Print all detected conflicts among selected events.
    """
    selected = load_selected_course_ids()
    events = _selected_events(selected, events_by_course_id)

    confs = find_conflicts(events)
    if not confs:
        print("No conflicts found.")
        return 0

    # sort conflicts by date/start for nicer output
    def key(pair: tuple[dict[str, Any], dict[str, Any]]) -> tuple[str, str]:
        a, b = pair
        return (str(a.get("date", "")), str(a.get("start", "")))

    confs_sorted = sorted(confs, key=key)

    print(f"Conflicts found: {len(confs_sorted)}")
    for a, b in confs_sorted:
        ad = a.get("date", "")
        astart = a.get("start", "")
        aend = a.get("end", "")
        at = a.get("title", "")
        acid = a.get("course_id", "")
        bd = b.get("date", "")
        bstart = b.get("start", "")
        bend = b.get("end", "")
        bt = b.get("title", "")
        bcid = b.get("course_id", "")

        print(f"- {ad} {astart}-{aend} {acid} {at}  <->  {bd} {bstart}-{bend} {bcid} {bt}")

    return 0


def _cmd_export(args: argparse.Namespace, events_by_course_id: dict[str, list[dict[str, Any]]]) -> int:
    """
    Export selected events into an iCalendar (.ics) file.
    """
    selected = load_selected_course_ids()
    events = _selected_events(selected, events_by_course_id)

    if not events:
        print("No selected events to export.")
        return 0

    out_path = (args.out or "").strip()
    if not out_path:
        print("Please provide output .ics path.")
        return 1

    n = export_events_to_ics(events, out_path)
    print(f"Exported {n} events to: {out_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """
    Build the argparse CLI parser with sub-commands.
    """
    parser = argparse.ArgumentParser(prog="myschedule", description="MySchedule CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="Search for courses")
    p_search.add_argument("text", type=str, help="Search text")

    p_add = sub.add_parser("add", help="Add course by course_id")
    p_add.add_argument("course_id", type=str, help="Course ID (e.g. FS261059)")

    p_remove = sub.add_parser("remove", help="Remove course by course_id")
    p_remove.add_argument("course_id", type=str, help="Course ID (e.g. FS261059)")

    sub.add_parser("conflicts", help="Show schedule conflicts among selected courses")

    p_export = sub.add_parser("export", help="Export selected events to .ics")
    p_export.add_argument("out", type=str, help="Output file path (e.g. out.ics)")

    sub.add_parser("interactive", help="Interactive menu mode")

    return parser


def main(argv: list[str] | None = None) -> None:
    """
    CLI entry point. Parses args, dispatches to command handlers,
    and exits via SystemExit with a return code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    courses, course_by_id, events_by_course_id = _build_indexes()

    if args.command == "search":
        raise SystemExit(_cmd_search(args, courses))
    if args.command == "add":
        raise SystemExit(_cmd_add(args, course_by_id))
    if args.command == "remove":
        raise SystemExit(_cmd_remove(args))
    if args.command == "conflicts":
        raise SystemExit(_cmd_conflicts(args, events_by_course_id))
    if args.command == "export":
        raise SystemExit(_cmd_export(args, events_by_course_id))

    if args.command == "interactive":
        from myschedule.interactive import run_interactive, build_indexes

        indexes = build_indexes()
        run_interactive(indexes, rebuild_indexes_fn=build_indexes)
        raise SystemExit(0)

    raise SystemExit(2)
