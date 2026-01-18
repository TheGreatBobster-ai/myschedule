from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import List, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Paths & URLs
# ---------------------------------------------------------------------------

PACKAGE_DIR = Path(__file__).resolve().parent
RAW_DIR = PACKAGE_DIR / "data" / "raw"

BASE_URL = "https://portal.unilu.ch"
SEARCH_URL = "https://portal.unilu.ch/search"


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _fetch_course_links(semester: str) -> List[Tuple[str, str]]:
    """
    Load semester search page and extract (course_id, detail_url).

    Returns:
        List of tuples: [(FS261269, https://portal.unilu.ch/details?code=FS261269), ...]
    """
    params = {"Semester": semester}
    resp = requests.get(SEARCH_URL, params=params, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    links: List[Tuple[str, str]] = []

    # IMPORTANT: links are relative and look like "details?code=FS261403"
    for a in soup.select("a[href^='details?code=']"):
        href = a.get("href")
        if not href:
            continue

        course_id = href.split("code=")[-1].strip()
        detail_url = urljoin(BASE_URL + "/", href)

        if course_id:
            links.append((course_id, detail_url))

    # Deduplicate & sort for stable output
    return sorted(set(links))


def scrape_semester(
    semester: str,
    refresh: bool = False,
    sleep_seconds: float = 0.2,
) -> None:
    """
    Scrape all course detail pages for one semester and cache them as HTML.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Scraping semester: {semester}")
    courses = _fetch_course_links(semester)

    print(f"Found {len(courses)} courses")

    for course_id, url in courses:
        out_file = RAW_DIR / f"{course_id}.html"

        if out_file.exists() and not refresh:
            print(f"SKIP  {course_id}")
            continue

        print(f"FETCH {course_id}")
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()

        out_file.write_text(resp.text, encoding="utf-8")
        time.sleep(sleep_seconds)

    print("Scraping finished.")


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="myschedule.scrape", description="Scrape UniLU course pages (cache HTML)")
    p.add_argument("--semester", "-s", type=str, default="FS26", help="Semester code (e.g., FS26, HS25)")
    p.add_argument("--refresh", action="store_true", help="Re-fetch and overwrite existing HTML files")
    p.add_argument("--sleep", type=float, default=0.2, help="Sleep seconds between requests")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    scrape_semester(args.semester.strip(), refresh=args.refresh, sleep_seconds=args.sleep)


if __name__ == "__main__":
    main()
