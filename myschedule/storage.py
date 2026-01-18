"""
Persistent storage for the user's course selection.

This module manages the file:

    data/processed/selected_courses.json

Design rationale:
- courses.json and events.json contain the complete scraped dataset
- selected_courses.json stores only the user's personal course choices

This separation ensures that user state is preserved independently
from repeated scraping and parsing operations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def _default_selected_path() -> Path:
    """
    Return the default path of selected_courses.json inside the package.

    This keeps all user-specific state colocated with the processed data
    and avoids hard-coded absolute paths.

    Using a function instead of a constant makes testing easier,
    because tests can override the path.
    """
    base_dir = Path(__file__).resolve().parent
    return base_dir / "data" / "processed" / "selected_courses.json"


def load_selected_course_ids(path: str | Path | None = None) -> set[str]:
    """
    Load selected course IDs from selected_courses.json.

    Returns an empty set if the file does not exist or is invalid.

    This function is deliberately defensive:
    it never crashes the application if the file is missing or corrupted.
    """
    # Use custom path if provided (mainly for tests),
    # otherwise fall back to the default package location
    selected_path = Path(path) if path is not None else _default_selected_path()

    # First run: file does not exist yet → no courses selected
    if not selected_path.exists():
        return set()

    try:
        data = json.loads(selected_path.read_text(encoding="utf-8"))
        ids = data.get("selected_course_ids", [])
        if not isinstance(ids, list):
            return set()
        # normalize: strip + uppercase, ignore non-strings
        out: set[str] = set()
        for x in ids:
            if isinstance(x, str):
                cid = x.strip().upper()
                if cid:
                    out.add(cid)
        return out
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, AttributeError):
        return set()


def save_selected_course_ids(ids: Iterable[str], path: str | Path | None = None) -> None:
    """
    Save selected course IDs to selected_courses.json.

    Creates parent directories if needed.

    All IDs are normalized before saving to guarantee a stable file format.
    """
    selected_path = Path(path) if path is not None else _default_selected_path()
    selected_path.parent.mkdir(parents=True, exist_ok=True)

    norm = sorted({str(x).strip().upper() for x in ids if str(x).strip()})
    payload = {"selected_course_ids": norm}

    selected_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
