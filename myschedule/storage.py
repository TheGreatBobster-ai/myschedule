"""
Storage for local user selection.

We store only selected course IDs in:
    data/processed/selected_courses.json

Reason:
- courses.json + events.json contain ALL scraped data
- selected_courses.json is the user's personal selection
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def _default_selected_path() -> Path:
    base_dir = Path(__file__).resolve().parent
    return base_dir / "data" / "processed" / "selected_courses.json"


def load_selected_course_ids(path: str | Path | None = None) -> set[str]:
    """
    Load selected course IDs from selected_courses.json.

    Returns an empty set if the file does not exist or is invalid.
    """
    selected_path = Path(path) if path is not None else _default_selected_path()

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
    """
    selected_path = Path(path) if path is not None else _default_selected_path()
    selected_path.parent.mkdir(parents=True, exist_ok=True)

    norm = sorted({str(x).strip().upper() for x in ids if str(x).strip()})
    payload = {"selected_course_ids": norm}

    selected_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
