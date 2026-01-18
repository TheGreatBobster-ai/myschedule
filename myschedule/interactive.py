from __future__ import annotations

import json
import subprocess
import sys
import time

from collections import Counter
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, date, timedelta

from pathlib import Path
from typing import Any, Callable, Optional

from myschedule.conflicts import find_conflicts
from myschedule.export_ics import export_events_to_ics
from myschedule.storage import load_selected_course_ids, save_selected_course_ids

# Optional rich
try:
    from rich.console import Console
    from rich.table import Table
    from rich import box
    from rich.progress import Progress, BarColumn, TimeRemainingColumn, TextColumn

    HAS_RICH = True
    console = Console()
except Exception:  # pragma: no cover
    HAS_RICH = False
    console = None


PACKAGE_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = PACKAGE_DIR / "data" / "processed"
RAW_DIR = PACKAGE_DIR / "data" / "raw"
META_PATH = PROCESSED_DIR / "metadata.json"


@dataclass
class Indexes:
    courses: list[dict[str, Any]]
    course_by_id: dict[str, dict[str, Any]]
    events_by_course_id: dict[str, list[dict[str, Any]]]


def _println(msg: str = "") -> None:
    if HAS_RICH:
        console.print(msg)
    else:
        print(msg)


def _prompt(msg: str) -> str:
    if HAS_RICH:
        return console.input(msg)
    return input(msg)


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _has_processed_data() -> bool:
    return (PROCESSED_DIR / "courses.json").exists() and (PROCESSED_DIR / "events.json").exists()


def build_indexes() -> Indexes:
    courses_path = PROCESSED_DIR / "courses.json"
    events_path = PROCESSED_DIR / "events.json"

    # Onboarding safety: no data yet
    if not courses_path.exists() or not events_path.exists():
        return Indexes(
            courses=[],
            course_by_id={},
            events_by_course_id=defaultdict(list),
        )

    courses_raw = _load_json(courses_path)
    events_raw = _load_json(events_path)

    courses: list[dict[str, Any]] = list(courses_raw) if isinstance(courses_raw, list) else []
    events: list[dict[str, Any]] = list(events_raw) if isinstance(events_raw, list) else []

    course_by_id: dict[str, dict[str, Any]] = {}
    for c in courses:
        cid = _safe_str(c.get("course_id")).strip().upper()
        if cid:
            course_by_id[cid] = c

    events_by_course_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in events:
        cid = _safe_str(e.get("course_id")).strip().upper()
        if cid:
            events_by_course_id[cid].append(e)

    return Indexes(
        courses=courses,
        course_by_id=course_by_id,
        events_by_course_id=events_by_course_id,
    )


def _read_metadata() -> dict[str, Any]:
    if not META_PATH.exists():
        return {}
    try:
        return json.loads(META_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_metadata(semester: str, courses_count: int, events_count: int) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "last_scraped": datetime.now().isoformat(timespec="seconds"),
        "semester": semester,
        "courses": courses_count,
        "events": events_count,
    }
    META_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _selected_events(
    selected_ids: set[str], events_by_course_id: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for cid in sorted(selected_ids):
        out.extend(events_by_course_id.get(cid, []))
    out.sort(key=lambda ev: (_safe_str(ev.get("date")), _safe_str(ev.get("start"))))
    return out


def run_interactive(indexes: Indexes, rebuild_indexes_fn: Callable[[], Indexes]) -> None:
    """
    Interactive menu loop with optional "Update data" (scrape+parse+reload).
    """

    # --- onboarding: ensure data exists ---
    if not _has_processed_data():
        _println("\nNo processed data found yet (courses.json / events.json).")
        _println("You need to run an initial scrape+parse once.")
        go = _prompt("Run [8] Update data now? [Y/n] (0 = back): ").strip().lower()

        if go == "0" or go == "n":
            _println("Returning to menu. You can run [8] Update data anytime.")
            return

        ok = _flow_update_data()
        if ok:
            indexes = rebuild_indexes_fn()
            _println("Data loaded. Welcome to MySchedule!")
        else:
            _println("Update was not completed. Returning to menu.")
            return
    # --- main menu loop ---

    while True:
        selected = load_selected_course_ids()
        events = _selected_events(selected, indexes.events_by_course_id)

        _print_header(selected, events)

        choice = _prompt(
            "\n[1] Search + add course\n"
            "[2] View selected courses\n"
            "[3] Remove a course\n"
            "[4] Show conflicts\n"
            "[5] Timetable (choose week)\n"
            "[6] Agenda (all dates)\n"
            "[7] Export .ics\n"
            "[8] Update data (re-scrape UniLU)\n"
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
            _flow_conflicts(indexes, events)
        elif choice == "5":
            _flow_timetable_week(events)
        elif choice == "6":
            _flow_agenda(events)
        elif choice == "7":
            _flow_export(events)
        elif choice == "8":
            ok = _flow_update_data()
            if ok:
                # Reload fresh JSON into memory
                indexes = rebuild_indexes_fn()
                _println("Data reloaded into interactive session.")
        else:
            _println("Invalid choice.")


def _print_header(selected: set[str], events: list[dict[str, Any]]) -> None:
    meta = _read_metadata()
    if meta:
        last = _safe_str(meta.get("last_scraped"))
        sem = _safe_str(meta.get("semester"))
        c = _safe_str(meta.get("courses"))
        e = _safe_str(meta.get("events"))
        _println(f"\n=== MySchedule (interactive) ===")
        _println(f"Data: semester={sem} | last_scraped={last} | courses={c} | events={e}")
    else:
        _println(f"\n=== MySchedule (interactive) ===")
        _println("Data: (no metadata yet) – run [8] Update data once to generate metadata.json")

    _println(f"Selected courses: {len(selected)} | Selected events: {len(events)}")


def _short_instructors(course: dict[str, Any]) -> str:
    instructors = course.get("instructors", [])
    if not instructors:
        return ""

    if not isinstance(instructors, list):
        instructors = [instructors]

    names = [str(x).strip() for x in instructors if str(x).strip()]
    if not names:
        return ""

    # Keep titles/grades, but cut noisy suffixes like "/ Executive MBA"
    first = names[0].split("/", 1)[0].strip()

    # Optional: shorten if too long (keeps table nice)
    MAX_LEN = 38
    if len(first) > MAX_LEN:
        first = first[: MAX_LEN - 1].rstrip() + "…"

    extra = len(names) - 1
    return f"{first} +{extra}" if extra > 0 else first


def _event_count_for_course(course_id: str, events_by_course_id: dict[str, list[dict[str, Any]]]) -> int:
    return len(events_by_course_id.get(course_id, []))


def _course_label(
    course: dict[str, Any], events_by_course_id: dict[str, list[dict[str, Any]]], rich: bool = False
) -> str:
    cid_raw = _safe_str(course.get("course_id")).strip().upper()
    title_raw = (_safe_str(course.get("title")) or "").strip() or "(no title)"

    instr_raw = _short_instructors(course)
    course_type_raw = _safe_str(course.get("type") or course.get("kind") or "").strip()
    n_events = _event_count_for_course(cid_raw, events_by_course_id)

    if rich and HAS_RICH:
        cid = f"[bold cyan]{cid_raw}[/]"
        title = title_raw  # keep neutral (readability)
        instr = f"[magenta]{instr_raw}[/]" if instr_raw else ""
        course_type = f"[green]{course_type_raw}[/]" if course_type_raw else ""
        evs = f"[yellow]{n_events}[/] events"
    else:
        cid = cid_raw
        title = title_raw
        instr = instr_raw
        course_type = course_type_raw
        evs = f"{n_events} events"

    bits = [cid, title]
    if instr:
        bits.append(instr)
    if course_type:
        bits.append(course_type)
    bits.append(evs)

    return " | ".join(bits)


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


def _conflicts_if_added(
    candidate_cid: str,
    selected_ids: set[str],
    events_by_course_id: dict[str, list[dict[str, Any]]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """
    Returns conflict pairs where one event is from the candidate course and
    the other event is from already selected courses.
    """
    cand_events = events_by_course_id.get(candidate_cid, [])
    if not cand_events or not selected_ids:
        return []

    selected_events: list[dict[str, Any]] = []
    for cid in selected_ids:
        selected_events.extend(events_by_course_id.get(cid, []))

    # Run your existing engine
    all_pairs = find_conflicts(selected_events + cand_events)

    # Filter to only pairs that involve candidate course vs selected courses
    out: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for a, b in all_pairs:
        a_c = _safe_str(a.get("course_id")).strip().upper()
        b_c = _safe_str(b.get("course_id")).strip().upper()
        if a_c == candidate_cid and b_c in selected_ids:
            out.append((a, b))
        elif b_c == candidate_cid and a_c in selected_ids:
            out.append((b, a))  # normalize: (candidate_event, other_event)
    return out


def _show_candidate_conflict_details(
    candidate_cid: str,
    pairs: list[tuple[dict[str, Any], dict[str, Any]]],
    indexes: Indexes,
) -> None:
    """
    Prints conflicts grouped by other course.
    pairs are normalized as (candidate_event, other_event).
    """
    if not pairs:
        _println("No conflicts.")
        return

    # group by other course id
    by_other: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for cand_ev, other_ev in pairs:
        other_cid = _safe_str(other_ev.get("course_id")).strip().upper()
        by_other[other_cid].append((cand_ev, other_ev))

    cand_course = indexes.course_by_id.get(candidate_cid, {"course_id": candidate_cid, "title": ""})
    cand_label = _course_label(cand_course, indexes.events_by_course_id)

    _println(f"\nConflicts for candidate course:\n- {cand_label}\n")

    # Overview
    for other_cid in sorted(by_other.keys()):
        other_course = indexes.course_by_id.get(other_cid, {"course_id": other_cid, "title": ""})
        other_label = _course_label(other_course, indexes.events_by_course_id)
        n = len(by_other[other_cid])
        _println(f"* {other_label}  →  {n} conflicts")

    # Details
    _println("\nDetails:")
    i = 1
    for other_cid in sorted(by_other.keys()):
        other_course = indexes.course_by_id.get(other_cid, {"course_id": other_cid, "title": ""})
        other_label = _course_label(other_course, indexes.events_by_course_id)
        _println(f"\n=== With: {other_label} ===")
        for cand_ev, other_ev in sorted(
            by_other[other_cid], key=lambda p: (_safe_str(p[0].get("date")), _safe_str(p[0].get("start")))
        ):
            left = _event_line(cand_ev)
            right = _event_line(other_ev)
            if HAS_RICH:
                _println(f"{i}) [red]{left}[/]  <->  [red]{right}[/]")
            else:
                _println(f"{i}) ! {left}  <->  ! {right}")
            i += 1

    _prompt("\nPress Enter to go back: ")


def _flow_search_add(indexes: Indexes, selected: set[str]) -> None:
    """
    Search courses and add them. After adding (or already-selected), ask whether
    user wants to add more courses without returning to main menu.
    """
    while True:
        query = _prompt("Search text or code (e.g., 'finance' or 'FS261107') [blank = back]: ").strip().lower()
        if not query:
            return

        matches: list[dict[str, Any]] = []
        for c in indexes.courses:
            cid = _safe_str(c.get("course_id")).strip().upper()
            title = (_safe_str(c.get("title")) or "").strip()
            instructors = c.get("instructors", [])
            instr_text = (
                " ".join([_safe_str(x) for x in instructors])
                if isinstance(instructors, list)
                else _safe_str(instructors)
            )
            hay = f"{cid} {title} {instr_text}".lower()
            if query in hay:
                matches.append(c)

        if not matches:
            _println("No results.")
            continue

        matches = matches[:20]

        if HAS_RICH:
            table = Table(title="Search results (max 20)", box=box.SIMPLE)
            table.add_column("#", justify="right")
            table.add_column("Course")
            for i, c in enumerate(matches, start=1):
                table.add_row(str(i), _course_label(c, indexes.events_by_course_id, rich=True))
            console.print(table)
        else:
            _println("Search results (max 20):")
            for i, c in enumerate(matches, start=1):
                _println(f"{i}) {_course_label(c, indexes.events_by_course_id)}")

        pick = _prompt("Enter number to add [blank = new search]: ").strip()
        if not pick:
            # user wants to search again
            continue
        if not pick.isdigit():
            _println("Not a number.")
            continue

        i = int(pick)
        if not (1 <= i <= len(matches)):
            _println("Out of range.")
            continue

        cid = _safe_str(matches[i - 1].get("course_id")).strip().upper()
        if not cid:
            _println("Invalid course_id.")
            continue

        if cid in selected:
            _println(f"Already selected: {cid}")
        else:
            # --- conflict preview before adding ---
            pairs = _conflicts_if_added(cid, selected, indexes.events_by_course_id)

            if pairs:
                other_courses = sorted({_safe_str(b.get("course_id")).strip().upper() for (_, b) in pairs})
                n_courses = len(other_courses)
                n_events = len(pairs)

                _println(
                    f"\n⚠️ This course conflicts with {n_courses} selected course(s), "
                    f"total {n_events} conflicting event overlap(s)."
                )

                # loop until user decides
                while True:
                    ans = _prompt("Add anyway? [Y]=add, [N]=cancel, [D]=details: ").strip().lower()
                    if ans == "y" or ans == "":
                        selected.add(cid)
                        save_selected_course_ids(selected)
                        _println(f"Added: {cid}")
                        break
                    if ans == "n" or ans == "0":
                        _println("Not added.")
                        break
                    if ans == "d":
                        _show_candidate_conflict_details(cid, pairs, indexes)
                        # then return here (same question again)
                        continue
                    _println("Invalid input.")
            else:
                selected.add(cid)
                save_selected_course_ids(selected)
                _println(f"Added: {cid}")

        more = _prompt("Add another course? [Y/n]: ").strip().lower()
        if more == "n":
            return
        # else loop continues (new search)


def _flow_view_selected(indexes: Indexes, selected: set[str]) -> None:
    if not selected:
        _println("No courses selected.")
        return

    if HAS_RICH:
        table = Table(title="Selected courses", box=box.SIMPLE)
        table.add_column("Course")

        for cid in sorted(selected):
            c = indexes.course_by_id.get(cid)
            if c:
                table.add_row(_course_label(c, indexes.events_by_course_id, rich=True))
            else:
                missing_events = len(indexes.events_by_course_id.get(cid, []))
                table.add_row(f"[bold cyan]{cid}[/] | (not found in courses.json) | {missing_events} events")

        console.print(table)
        return

    # Fallback: plain terminal output
    items: list[str] = []
    for cid in sorted(selected):
        c = indexes.course_by_id.get(cid)
        if c:
            items.append(_course_label(c, indexes.events_by_course_id))
        else:
            items.append(
                f"{cid} | (not found in courses.json) | {len(indexes.events_by_course_id.get(cid, []))} events"
            )

    _println("Selected courses:")
    for x in items:
        _println(f"- {x}")


def _flow_remove(indexes: Indexes, selected: set[str]) -> None:
    if not selected:
        _println("No courses selected.")
        return

    while True:
        if not selected:
            _println("No courses selected.")
            return

        ids = sorted(selected)

        if HAS_RICH:
            table = Table(title="Remove course", box=box.SIMPLE)
            table.add_column("#", justify="right")
            table.add_column("Course")
            for i, cid in enumerate(ids, start=1):
                c = indexes.course_by_id.get(cid, {"course_id": cid, "title": ""})
                table.add_row(str(i), _course_label(c, indexes.events_by_course_id, rich=True))
            console.print(table)
        else:
            _println("Remove course:")
            for i, cid in enumerate(ids, start=1):
                c = indexes.course_by_id.get(cid, {"course_id": cid, "title": ""})
                _println(f"{i}) {_course_label(c, indexes.events_by_course_id)}")

        pick = _prompt("Enter number to remove (or blank to cancel): ").strip()
        if not pick:
            return
        if not pick.isdigit():
            _println("Not a number.")
            continue

        idx = int(pick)
        if not (1 <= idx <= len(ids)):
            _println("Out of range.")
            continue

        cid = ids[idx - 1]
        selected.remove(cid)
        save_selected_course_ids(selected)
        _println(f"Removed: {cid}")

        more = _prompt("Remove another course? [Y/n]: ").strip().lower()
        if more == "n":
            return
        # else: loop continues and shows updated list


def _flow_conflicts(indexes: Indexes, events: list[dict[str, Any]]) -> None:
    if not events:
        _println("No selected events.")
        return

    confs = find_conflicts(events)
    if not confs:
        _println("No conflicts found.")
        return

    # Sort for stable order
    confs = sorted(confs, key=lambda p: (_safe_str(p[0].get("date")), _safe_str(p[0].get("start"))))

    def _course_pair_label(cid: str, rich: bool) -> str:
        c = indexes.course_by_id.get(cid, {"course_id": cid, "title": "", "type": ""})

        title = (_safe_str(c.get("title")) or "").strip()
        ctype = (_safe_str(c.get("type")) or "").strip()

        if rich and HAS_RICH:
            cid_s = f"[bold cyan]{cid}[/]"
            title_s = title
            type_s = f"[green]{ctype}[/]" if ctype else ""
        else:
            cid_s = cid
            title_s = title
            type_s = ctype

        parts = [cid_s]
        if title_s:
            parts.append(title_s)
        if type_s:
            parts.append(type_s)

        return " | ".join(parts)

    def _pair_key(a: dict[str, Any], b: dict[str, Any]) -> tuple[str, str]:
        ca = _safe_str(a.get("course_id")).strip().upper()
        cb = _safe_str(b.get("course_id")).strip().upper()
        return (ca, cb) if ca <= cb else (cb, ca)

    # Group conflicts by course-pair
    by_pair: dict[tuple[str, str], list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    involved_courses: set[str] = set()

    for a, b in confs:
        ca = _safe_str(a.get("course_id")).strip().upper()
        cb = _safe_str(b.get("course_id")).strip().upper()
        if not ca or not cb:
            continue
        involved_courses.add(ca)
        involved_courses.add(cb)
        by_pair[_pair_key(a, b)].append((a, b))

    pairs_sorted = sorted(by_pair.items(), key=lambda item: (-len(item[1]), item[0]))

    total_confs = len(confs)
    total_courses = len(involved_courses)

    _println(f"Conflicts found: {total_confs}")
    _println(f"Courses involved in conflicts: {total_courses}")

    # Loop so user can inspect multiple pairs without re-entering menu
    while True:
        _println("\nConflict overview (by course pair):")

        if HAS_RICH:
            table = Table(box=box.SIMPLE, title="Conflict pairs")
            table.add_column("#", justify="right")
            table.add_column("Pair")
            table.add_column("Conflicts", justify="right")

            for i, ((c1, c2), lst) in enumerate(pairs_sorted, start=1):
                pair_label = f"{_course_pair_label(c1, rich=True)}  ↔  {_course_pair_label(c2, rich=True)}"
                table.add_row(str(i), pair_label, f"[yellow]{len(lst)}[/]")

            table.add_row(str(len(pairs_sorted) + 1), "[bold]Show ALL conflicts[/]", f"[yellow]{total_confs}[/]")
            console.print(table)
        else:
            for i, ((c1, c2), lst) in enumerate(pairs_sorted, start=1):
                _println(
                    f"{i}) {_course_pair_label(c1, rich=False)}  <->  {_course_pair_label(c2, rich=False)}  ({len(lst)} conflicts)"
                )
            _println(f"{len(pairs_sorted)+1}) Show ALL conflicts ({total_confs})")

        pick = _prompt("Select number for details, or 0 to go back: ").strip()
        if pick == "0" or pick == "":
            return
        if not pick.isdigit():
            _println("Not a number.")
            continue

        choice = int(pick)
        if choice == len(pairs_sorted) + 1:
            # Show all conflicts in detail
            _println(f"\n=== All conflicts ({total_confs}) ===")
            for k, (a, b) in enumerate(confs, start=1):
                _println(f"{k}. {_safe_str(a.get('date'))}: {_event_line(a)}  <->  {_event_line(b)}")
            _prompt("\nPress Enter to go back...")
            continue

        if not (1 <= choice <= len(pairs_sorted)):
            _println("Out of range.")
            continue

        (c1, c2), lst = pairs_sorted[choice - 1]
        _println(f"\n=== Conflicts: {c1} ↔ {c2} ({len(lst)}) ===")
        for k, (a, b) in enumerate(lst, start=1):
            _println(f"{k}. {_safe_str(a.get('date'))}: {_event_line(a)}  <->  {_event_line(b)}")

        _prompt("\nPress Enter to go back...")


def _flow_agenda(events: list[dict[str, Any]]) -> None:
    if not events:
        _println("No selected events.")
        return

    # --- build conflict markers ---
    conf_pairs = find_conflicts(events)

    def event_key(ev: dict[str, Any]) -> tuple[str, str, str, str]:
        return (
            _safe_str(ev.get("date")),
            _safe_str(ev.get("start")),
            _safe_str(ev.get("end")),
            _safe_str(ev.get("course_id")),
        )

    conflict_keys: set[tuple[str, str, str, str]] = set()
    for a, b in conf_pairs:
        conflict_keys.add(event_key(a))
        conflict_keys.add(event_key(b))

    def fmt_event(ev: dict[str, Any]) -> str:
        txt = _event_line(ev)
        if event_key(ev) in conflict_keys:
            if HAS_RICH:
                return f"[red]{txt}[/]"
            return f"! {txt}"
        return txt

    # --- group by date ---
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ev in events:
        d = _safe_str(ev.get("date")).strip()
        if d:
            by_date[d].append(ev)

    def weekday_short(d: date) -> str:
        names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return names[d.weekday()]

    def parse_date(s: str) -> Optional[date]:
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None

    def week_key(d: date) -> tuple[int, int]:
        iso = d.isocalendar()
        return (iso.year, iso.week)

    # sort all dates
    sorted_dates = sorted(by_date.keys())

    # build mapping week -> dates
    week_to_dates: dict[tuple[int, int], list[str]] = defaultdict(list)
    for ds in sorted_dates:
        dd = parse_date(ds)
        if dd is None:
            continue
        week_to_dates[week_key(dd)].append(ds)

    weeks = sorted(week_to_dates.keys())

    # UX params
    WEEKS_PER_PAGE = 4

    # legend
    if conflict_keys:
        if HAS_RICH:
            _println("Legend: [red]CONFLICT[/] = overlaps detected")
        else:
            _println("Legend: ! = conflict (overlap)")

    # menu: allow show all or paged
    mode = _prompt("\nAgenda mode: [Enter]=paged (4 weeks), [A]=show all, [0]=back: ").strip().lower()
    if mode == "0":
        return
    show_all = mode == "a"

    idx = 0
    while idx < len(weeks):
        # decide which weeks to show this page
        page_weeks = weeks[idx:] if show_all else weeks[idx : idx + WEEKS_PER_PAGE]

        for y, w in page_weeks:
            # week header
            mon = date.fromisocalendar(y, w, 1)
            sun = mon + timedelta(days=6)
            if HAS_RICH:
                _println(
                    f"\n[bold cyan]=== {y}-W{w:02d} ({mon.isoformat()} → {sun.isoformat()}) ==============================[/]"
                )
            else:
                _println(f"\n=== {y}-W{w:02d} ({mon.isoformat()} → {sun.isoformat()}) ===")

            # dates inside week
            for ds in week_to_dates[(y, w)]:
                dd = parse_date(ds)
                if dd:
                    _println(f"\n{ds} ({weekday_short(dd)})")
                else:
                    _println(f"\n{ds}")

                for ev in sorted(by_date[ds], key=lambda x: _safe_str(x.get("start"))):
                    _println(f"  - {fmt_event(ev)}")

        if show_all:
            return  # done

        idx += WEEKS_PER_PAGE
        if idx >= len(weeks):
            return

        # paging controls
        more = _prompt("\nPress Enter to load more, or 0 to return to menu: ").strip()
        if more == "0":
            return


def _flow_timetable_week(events: list[dict[str, Any]]) -> None:
    if not events:
        _println("No selected events.")
        return

    def parse_date(s: str) -> Optional[date]:
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None

    def week_key(d: date) -> tuple[int, int]:
        iso = d.isocalendar()
        return (iso.year, iso.week)

    def weekday_short(d: date) -> str:
        names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return names[d.weekday()]

    def week_range_label(y: int, w: int) -> str:
        # ISO week starts Monday = 1
        mon = date.fromisocalendar(y, w, 1)
        sun = mon + timedelta(days=6)
        return f"{y}-W{w:02d} ({mon.isoformat()} → {sun.isoformat()})"

    # collect all valid dates
    dates: list[date] = []
    for ev in events:
        dd = parse_date(_safe_str(ev.get("date")))
        if dd:
            dates.append(dd)

    if not dates:
        _println("No valid event dates.")
        return

    weeks = sorted({week_key(d) for d in dates})

    # Loop so user can view multiple weeks without re-entering menu
    while True:

        _println("\nAvailable weeks:")

        # Precompute conflicts per week (for display)
        week_conf_count: dict[tuple[int, int], int] = {}
        for yw in weeks:
            yy, ww = yw
            wk_events = []
            for ev in events:
                dd = parse_date(_safe_str(ev.get("date")))
                if dd and week_key(dd) == (yy, ww):
                    wk_events.append(ev)
            week_conf_count[yw] = len(find_conflicts(wk_events))

        for i, (y, w) in enumerate(weeks, start=1):
            label = week_range_label(y, w)
            nconf = week_conf_count.get((y, w), 0)

            if HAS_RICH:
                conf_txt = f"[red]{nconf} conflicts[/]" if nconf > 0 else "[green]0 conflicts[/]"
                _println(f"{i:>2}) {label}  |  {conf_txt}")
            else:
                _println(f"{i}) {label}  |  {nconf} conflicts")

        pick = _prompt("Choose week number (blank = first, 0 = back): ").strip()
        if pick == "0":
            return

        if pick and pick.isdigit() and 1 <= int(pick) <= len(weeks):
            y, w = weeks[int(pick) - 1]
        else:
            y, w = weeks[0]

        # filter events for this week
        week_events: list[dict[str, Any]] = []
        for ev in events:
            dd = parse_date(_safe_str(ev.get("date")))
            if dd and week_key(dd) == (y, w):
                week_events.append(ev)

        if not week_events:
            _println("No events in that week.")
            continue

        # detect conflicts within that week (mark conflict events)
        conf_pairs = find_conflicts(week_events)

        def event_key(ev: dict[str, Any]) -> tuple[str, str, str, str]:
            # stable key, event_id may not exist everywhere
            return (
                _safe_str(ev.get("date")),
                _safe_str(ev.get("start")),
                _safe_str(ev.get("end")),
                _safe_str(ev.get("course_id")),
            )

        conflict_keys: set[tuple[str, str, str, str]] = set()
        for a, b in conf_pairs:
            conflict_keys.add(event_key(a))
            conflict_keys.add(event_key(b))

        def fmt_event(ev: dict[str, Any], rich: bool) -> str:
            txt = _event_line(ev)
            if event_key(ev) in conflict_keys:
                if rich and HAS_RICH:
                    return f"[red]{txt}[/]"
                return f"! {txt}"  # plain fallback
            return txt

        # bucket by weekday incl Saturday
        buckets = {name: [] for name in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]}
        for ev in sorted(week_events, key=lambda x: (_safe_str(x.get("date")), _safe_str(x.get("start")))):
            dd = parse_date(_safe_str(ev.get("date")))
            if not dd:
                continue
            wd = weekday_short(dd)
            if wd in buckets:
                buckets[wd].append(ev)

        # header with date range
        mon = date.fromisocalendar(y, w, 1)
        sun = mon + timedelta(days=6)
        _println(f"\n=== Timetable {y}-W{w:02d} ({mon.isoformat()} → {sun.isoformat()}) ===")

        # legend (only if conflicts exist)
        if conflict_keys:
            if HAS_RICH:
                _println("Legend: [red]CONFLICT[/] = overlaps detected in this week")
            else:
                _println("Legend: ! = conflict (overlap)")

        if HAS_RICH:
            table = Table(box=box.SIMPLE)
            for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]:
                table.add_column(day)

            def day_cell(day: str) -> str:
                if not buckets[day]:
                    return ""
                # blank line between events for readability
                return "\n\n".join(fmt_event(ev, rich=True) for ev in buckets[day])

            table.add_row(*(day_cell(d) for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]))
            console.print(table)

        else:
            cols = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
            col_width = 38
            header = " | ".join([c.ljust(col_width) for c in cols])
            _println(header)
            _println("-" * len(header))

            def day_cell_plain(day: str) -> str:
                if not buckets[day]:
                    return ""
                return "\n\n".join(fmt_event(ev, rich=False) for ev in buckets[day])

            row = []
            for c in cols:
                txt = day_cell_plain(c)
                row.append(txt[:col_width].ljust(col_width))

            _println(" | ".join(row))

        # flow control
        after = _prompt("\nPress Enter to choose another week, or 0 to return to menu: ").strip()
        if after == "0":
            return
        # else loop continues (back to week list)


def _flow_export(events: list[dict[str, Any]]) -> None:
    if not events:
        _println("No selected events.")
        return

    # Default to user's Downloads folder (works on Windows/macOS/Linux)
    downloads = Path.home() / "Downloads"
    default_name = "myschedule.ics"
    default_path = downloads / default_name

    choice = _prompt(f"Export location: [Enter]=Downloads/{default_name}, [P]=custom path, [0]=back: ").strip().lower()

    if choice == "0":
        return

    if choice == "p":
        # User can enter either:
        # - a filename (we put it into Downloads)
        # - or a full/relative path
        user_path = _prompt("Enter file name or full path (e.g. my.ics or C:\\temp\\my.ics): ").strip()
        if not user_path:
            out_path = default_path
        else:
            p = Path(user_path).expanduser()

            # If only a filename is given (no parent), store in Downloads
            if str(p.parent) in (".", ""):
                out_path = downloads / p.name
            else:
                out_path = p
    else:
        # default Downloads
        out_in = _prompt(f"File name in Downloads [default: {default_name}]: ").strip()
        out_path = downloads / out_in if out_in else default_path

    # enforce .ics extension
    if out_path.suffix.lower() != ".ics":
        out_path = out_path.with_suffix(".ics")

    # --- Deduplicate events (avoid double exports) ---
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for ev in events:
        key = _safe_str(ev.get("event_id")).strip()
        if not key:
            key = (
                f"{_safe_str(ev.get('course_id'))}|{_safe_str(ev.get('date'))}|"
                f"{_safe_str(ev.get('start'))}|{_safe_str(ev.get('end'))}"
            )
        if key in seen:
            continue
        seen.add(key)
        unique.append(ev)
    events = unique

    n = export_events_to_ics(events, out_path)
    abs_path = out_path.resolve()

    _println(f"\nExported {n} events.")
    _println(f"Saved to: {abs_path}")

    _println(
        "\nNext steps:\n"
        "- Google Calendar (desktop): Settings → Import & export → Import → choose this .ics file\n"
        "- iPhone/Android: send the .ics file to yourself (Mail/WhatsApp/AirDrop) and tap to import\n"
    )

    # Offer to open folder in Windows Explorer
    open_now = _prompt("Open folder now? [Y/n]: ").strip().lower()
    if open_now != "n":
        try:
            if sys.platform.startswith("win"):
                subprocess.run(["explorer.exe", "/select,", str(abs_path)], check=False)
            else:
                subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(abs_path.parent)], check=False)
        except Exception:
            pass


def _flow_update_data() -> bool:
    """
    Runs scrape + parse as subprocesses using the current venv Python.
    Streams output live. Writes metadata.json afterwards.

    UX improvements:
    - 0 = back at each step
    - confirm screen before long scrape
    - clear explanation of refresh behavior + processed overwrite
    - Ctrl+C abort handling
    """
    # Step 1: semester
    semester_in = _prompt("Semester [FS26] (0 = back): ").strip()
    if semester_in == "0":
        return False
    semester = semester_in or "FS26"

    _println(
        "\nAbout update:\n"
        "- Raw HTML cache: stored in myschedule/data/raw/\n"
        "- Processed JSON: courses/events are rebuilt and OVERWRITTEN each time.\n"
        "- Your selected courses (selected_courses.json) stay unchanged.\n"
    )

    # Step 2: refresh explanation + input
    _println(
        "Refresh option:\n"
        "- [Y] Refresh = re-download ALL course pages and overwrite existing HTML files.\n"
        "- [N] No refresh = keep existing HTML files (SKIP) and only fetch missing ones.\n"
        "Note: We do NOT delete old raw files. If UniLU removes a course, old HTML may remain.\n"
    )

    refresh_in = _prompt("Refresh (overwrite raw HTML)? [Y/n] (0 = back): ").strip().lower()
    if refresh_in == "0":
        return False
    refresh = refresh_in != "n"

    # Step 3: confirm long run
    _println(
        "\nThis may take ~10–15 minutes depending on semester size and connection.\n"
        "You can abort anytime with Ctrl+C.\n"
        "If you abort during scraping, some files may be updated while others stay old.\n"
    )
    confirm = _prompt("Start update now? [Y/n] (0 = back): ").strip().lower()
    if confirm == "0":
        return False
    if confirm == "n":
        _println("Update cancelled.")
        return False

    # Run scraper
    _println("\nRunning scraper... (Ctrl+C to abort)")
    ok = _run_scrape_subprocess(semester=semester, refresh=refresh)
    if not ok:
        _println("Scrape failed or was aborted. Update cancelled (processed data not rebuilt).")
        return False

    # Run parser
    _println("\nRunning parser... (Ctrl+C to abort)")
    ok = _run_parse_subprocess()
    if not ok:
        _println("Parse failed or was aborted. Processed JSON may be incomplete.")
        return False

    # After parse, count courses/events and write metadata
    try:
        courses = _load_json(PROCESSED_DIR / "courses.json")
        events = _load_json(PROCESSED_DIR / "events.json")
        c_count = len(courses) if isinstance(courses, list) else 0
        e_count = len(events) if isinstance(events, list) else 0
        _write_metadata(semester=semester, courses_count=c_count, events_count=e_count)
        _println(f"\nUpdate done. courses={c_count} events={e_count}")
    except Exception as e:
        _println(f"Update done, but failed to write metadata: {e}")

    return True


def _run_scrape_subprocess(semester: str, refresh: bool) -> bool:
    """
    Runs: python -u -m myschedule.scrape --semester FS26 --refresh
    Streams stdout line-by-line. Shows live progress.

    Ctrl+C aborts cleanly:
    - terminates scraper process
    - returns False to caller
    """
    cmd = [sys.executable, "-u", "-m", "myschedule.scrape", "--semester", semester]
    if refresh:
        cmd.append("--refresh")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    total: Optional[int] = None
    done = 0

    try:
        if HAS_RICH:
            progress = Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total}"),
                TimeRemainingColumn(),
                console=console,
            )

            task = progress.add_task("Scraping...", total=1)

            with progress:
                assert proc.stdout is not None
                for line in proc.stdout:
                    line = line.rstrip("\n")

                    # Detect total number of courses
                    if line.startswith("Found ") and " courses" in line:
                        try:
                            total = int(line.split("Found ")[1].split(" courses")[0].strip())
                            progress.update(task, total=total, completed=0)
                        except Exception:
                            pass

                    # Each course = one progress step
                    if line.startswith("FETCH ") or line.startswith("SKIP"):
                        done += 1
                        progress.update(task, completed=done)

                    console.print(line)

                rc = proc.wait()
                return rc == 0

        else:
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.rstrip("\n")
                if line.startswith("FETCH ") or line.startswith("SKIP"):
                    done += 1
                    if total:
                        _println(f"[{done}/{total}] {line}")
                    else:
                        _println(line)
                else:
                    _println(line)

            rc = proc.wait()
            return rc == 0

    except KeyboardInterrupt:
        _println("\nAborted by user (Ctrl+C). Stopping scraper...")
        try:
            proc.terminate()
        except Exception:
            pass
        return False


def _run_parse_subprocess() -> bool:
    cmd = [sys.executable, "-u", "-m", "myschedule.parse"]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            _println(line.rstrip("\n"))
        rc = proc.wait()
        return rc == 0
    except KeyboardInterrupt:
        _println("\nAborted by user (Ctrl+C). Stopping parser...")
        try:
            proc.terminate()
        except Exception:
            pass
        return False
