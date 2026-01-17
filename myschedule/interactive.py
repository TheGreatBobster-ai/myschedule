from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable

from myschedule.conflicts import find_conflicts
from myschedule.export_ics import export_events_to_ics
from myschedule.storage import load_selected_course_ids, save_selected_course_ids


# ---- Optional rich support (auto fallback) ----
try:
    from rich.console import Console
    from rich.table import Table
    from rich import box

    HAS_RICH = True
    console = Console()
except Exception:  # pragma: no cover
    HAS_RICH = False
    console = None


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x)


def _parse_date(d: str) -> date:
    return datetime.strptime(d, "%Y-%m-%d").date()


def _event_sort_key(ev: dict[str, Any]) -> tuple[str, str]:
    return (_safe_str(ev.get("date")), _safe_str(ev.get("start")))


def _course_label(course: dict[str, Any]) -> str:
    cid = _safe_str(course.get("course_id")).strip()
    title = (_safe_str(course.get("title")) or "").strip() or "(no title)"
    instructors = course.get("instructors", [])
    if isinstance(instructors, list):
        instr = ", ".join([_safe_str(x) for x in instructors if _safe_str(x).strip()])
    else:
        instr = _safe_str(instructors)
    instr = instr.strip()
    if instr:
        return f"{cid} | {title} | {instr}"
    return f"{cid} | {title}"


def _event_line(ev: dict[str, Any]) -> str:
    cid = _safe_str(ev.get("course_id")).strip()
    title = (_safe_str(ev.get("title")) or "").strip()
    start = _safe_str(ev.get("start")).strip()
    end = _safe_str(ev.get("end")).strip()
    loc = (_safe_str(ev.get("location")) or "").strip()
    kind = (_safe_str(ev.get("kind")) or "").strip()
    bits = [f"{start}-{end}", cid, title]
    if kind:
        bits.append(f"({kind})")
    if loc:
        bits.append(f"@ {loc}")
    return " | ".join([b for b in bits if b])


def _week_key(d: date) -> tuple[int, int]:
    iso = d.isocalendar()
    return (iso.year, iso.week)


def _weekday_short(d: date) -> str:
    # Monday=0..Sunday=6
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return names[d.weekday()]


@dataclass(frozen=True)
class Indexes:
    courses: list[dict[str, Any]]
    course_by_id: dict[str, dict[str, Any]]
    events_by_course_id: dict[str, list[dict[str, Any]]]


def run_interactive(indexes: Indexes) -> None:
    """
    Interactive menu loop. Safe to run without external dependencies.
    Uses rich automatically if installed.
    """
    while True:
        selected = load_selected_course_ids()
        selected_events = _gather_selected_events(selected, indexes.events_by_course_id)

        _print_header(selected, selected_events)

        choice = _prompt(
            "\n[1] Search + add course\n"
            "[2] View selected courses\n"
            "[3] Remove a course\n"
            "[4] Show conflicts\n"
            "[5] Timetable (choose week)\n"
            "[6] Agenda (all dates)\n"
            "[7] Export .ics\n"
            "[0] Exit\n"
            "Select: "
        ).strip()

        if choice == "0":
            _println("Bye.")
            return

        if choice == "1":
            _flow_search_add(indexes, selected)

        elif choice == "2":
            _flow_view_selected(indexes, selected)

        elif choice == "3":
            _flow_remove(indexes, selected)

        elif choice == "4":
            _flow_conflicts(selected_events)

        elif choice == "5":
            _flow_timetable_week(selected_events)

        elif choice == "6":
            _flow_agenda(selected_events)

        elif choice == "7":
            _flow_export(selected_events)

        else:
            _println("Invalid choice.")


def _println(msg: str) -> None:
    if HAS_RICH:
        console.print(msg)
    else:
        print(msg)


def _prompt(msg: str) -> str:
    if HAS_RICH:
        return console.input(msg)
    return input(msg)


def _print_header(selected: set[str], events: list[dict[str, Any]]) -> None:
    _println("\n=== MySchedule (interactive) ===")
    _println(f"Selected courses: {len(selected)} | Selected events: {len(events)}")


def _gather_selected_events(
    selected_ids: set[str], events_by_course_id: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for cid in sorted(selected_ids):
        out.extend(events_by_course_id.get(cid, []))
    return sorted(out, key=_event_sort_key)


def _flow_search_add(indexes: Indexes, selected: set[str]) -> None:
    query = _prompt("Search text (e.g., finance): ").strip().lower()
    if not query:
        _println("No search text.")
        return

    matches: list[dict[str, Any]] = []
    for c in indexes.courses:
        cid = _safe_str(c.get("course_id")).strip().upper()
        title = (_safe_str(c.get("title")) or "").strip()
        instructors = c.get("instructors", [])
        instr_text = (
            " ".join([_safe_str(x) for x in instructors]) if isinstance(instructors, list) else _safe_str(instructors)
        )
        hay = f"{cid} {title} {instr_text}".lower()
        if query in hay:
            matches.append(c)

    if not matches:
        _println("No results.")
        return

    matches = matches[:20]

    if HAS_RICH:
        table = Table(title="Search results (max 20)", box=box.SIMPLE)
        table.add_column("#", justify="right")
        table.add_column("Course")
        for i, c in enumerate(matches, start=1):
            table.add_row(str(i), _course_label(c))
        console.print(table)
    else:
        _println("Search results (max 20):")
        for i, c in enumerate(matches, start=1):
            _println(f"{i}) {_course_label(c)}")

    pick = _prompt("Enter number to add (or blank to cancel): ").strip()
    if not pick:
        return
    if not pick.isdigit():
        _println("Not a number.")
        return

    i = int(pick)
    if not (1 <= i <= len(matches)):
        _println("Out of range.")
        return

    cid = _safe_str(matches[i - 1].get("course_id")).strip().upper()
    if not cid:
        _println("Invalid course_id.")
        return

    if cid in selected:
        _println(f"Already selected: {cid}")
        return

    selected.add(cid)
    save_selected_course_ids(selected)
    _println(f"Added: {cid}")


def _flow_view_selected(indexes: Indexes, selected: set[str]) -> None:
    if not selected:
        _println("No courses selected.")
        return

    items = []
    for cid in sorted(selected):
        c = indexes.course_by_id.get(cid)
        if c:
            items.append(_course_label(c))
        else:
            items.append(f"{cid} | (not found in courses.json)")

    if HAS_RICH:
        table = Table(title="Selected courses", box=box.SIMPLE)
        table.add_column("Course")
        for x in items:
            table.add_row(x)
        console.print(table)
    else:
        _println("Selected courses:")
        for x in items:
            _println(f"- {x}")


def _flow_remove(indexes: Indexes, selected: set[str]) -> None:
    if not selected:
        _println("No courses selected.")
        return

    # show list
    ids = sorted(selected)
    if HAS_RICH:
        table = Table(title="Remove course", box=box.SIMPLE)
        table.add_column("#", justify="right")
        table.add_column("Course")
        for i, cid in enumerate(ids, start=1):
            c = indexes.course_by_id.get(cid, {"course_id": cid, "title": ""})
            table.add_row(str(i), _course_label(c))
        console.print(table)
    else:
        _println("Remove course:")
        for i, cid in enumerate(ids, start=1):
            c = indexes.course_by_id.get(cid, {"course_id": cid, "title": ""})
            _println(f"{i}) {_course_label(c)}")

    pick = _prompt("Enter number to remove (or blank to cancel): ").strip()
    if not pick:
        return
    if not pick.isdigit():
        _println("Not a number.")
        return
    i = int(pick)
    if not (1 <= i <= len(ids)):
        _println("Out of range.")
        return

    cid = ids[i - 1]
    selected.remove(cid)
    save_selected_course_ids(selected)
    _println(f"Removed: {cid}")


def _flow_conflicts(events: list[dict[str, Any]]) -> None:
    if not events:
        _println("No selected events.")
        return

    confs = find_conflicts(events)
    if not confs:
        _println("No conflicts found.")
        return

    confs = sorted(confs, key=lambda p: (_safe_str(p[0].get("date")), _safe_str(p[0].get("start"))))
    _println(f"Conflicts found: {len(confs)}")
    for a, b in confs:
        _println(f"- {_safe_str(a.get('date'))}: {_event_line(a)}  <->  {_event_line(b)}")


def _flow_agenda(events: list[dict[str, Any]]) -> None:
    if not events:
        _println("No selected events.")
        return

    # group by date
    by_date: dict[str, list[dict[str, Any]]] = {}
    for ev in events:
        d = _safe_str(ev.get("date")).strip()
        by_date.setdefault(d, []).append(ev)

    for d in sorted(by_date.keys()):
        try:
            dd = _parse_date(d)
            _println(f"\n{d} ({_weekday_short(dd)})")
        except Exception:
            _println(f"\n{d}")
        for ev in sorted(by_date[d], key=lambda x: _safe_str(x.get("start"))):
            _println(f"  - {_event_line(ev)}")


def _flow_timetable_week(events: list[dict[str, Any]]) -> None:
    if not events:
        _println("No selected events.")
        return

    # determine available weeks
    dates = []
    for ev in events:
        d = _safe_str(ev.get("date")).strip()
        if not d:
            continue
        try:
            dates.append(_parse_date(d))
        except Exception:
            continue

    if not dates:
        _println("No valid event dates.")
        return

    weeks = sorted({_week_key(d) for d in dates})
    # show week list
    _println("\nAvailable weeks:")
    for i, (y, w) in enumerate(weeks, start=1):
        _println(f"{i}) {y}-W{w:02d}")

    pick = _prompt("Choose week number (or blank = first): ").strip()
    if pick and pick.isdigit() and 1 <= int(pick) <= len(weeks):
        y, w = weeks[int(pick) - 1]
    else:
        y, w = weeks[0]

    # filter events in that ISO week
    week_events = []
    for ev in events:
        d = _safe_str(ev.get("date")).strip()
        try:
            dd = _parse_date(d)
        except Exception:
            continue
        if _week_key(dd) == (y, w):
            week_events.append(ev)

    if not week_events:
        _println("No events in that week.")
        return

    # group by weekday (Mon-Fri)
    buckets = {name: [] for name in ["Mon", "Tue", "Wed", "Thu", "Fri"]}
    for ev in sorted(week_events, key=_event_sort_key):
        d = _safe_str(ev.get("date")).strip()
        try:
            dd = _parse_date(d)
            wd = _weekday_short(dd)
        except Exception:
            continue
        if wd in buckets:
            buckets[wd].append(ev)

    # "Grid-ish" column view (robust text)
    _println(f"\n=== Timetable {y}-W{w:02d} ===")
    if HAS_RICH:
        table = Table(box=box.SIMPLE)
        for day in ["Mon", "Tue", "Wed", "Thu", "Fri"]:
            table.add_column(day)
        # max rows = max events per day
        max_len = max(len(buckets[d]) for d in buckets)
        for r in range(max_len):
            row = []
            for day in ["Mon", "Tue", "Wed", "Thu", "Fri"]:
                if r < len(buckets[day]):
                    row.append(_event_line(buckets[day][r]))
                else:
                    row.append("")
            table.add_row(*row)
        console.print(table)
    else:
        # plain text columns with padding
        cols = ["Mon", "Tue", "Wed", "Thu", "Fri"]
        col_width = 38
        lines: list[str] = []
        header = " | ".join([c.ljust(col_width) for c in cols])
        lines.append(header)
        lines.append("-" * len(header))
        max_len = max(len(buckets[d]) for d in buckets)
        for r in range(max_len):
            parts = []
            for c in cols:
                txt = _event_line(buckets[c][r]) if r < len(buckets[c]) else ""
                parts.append(txt[:col_width].ljust(col_width))
            lines.append(" | ".join(parts))
        _println("\n".join(lines))


def _flow_export(events: list[dict[str, Any]]) -> None:
    if not events:
        _println("No selected events.")
        return
    out = _prompt("Output path (e.g., out.ics): ").strip()
    if not out:
        _println("Cancelled.")
        return
    n = export_events_to_ics(events, out)
    _println(f"Exported {n} events to: {out}")
