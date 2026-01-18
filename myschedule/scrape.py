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

# Path to the folder where this file (scrape.py) is located
PACKAGE_DIR = Path(__file__).resolve().parent

# Folder where all downloaded HTML files will be stored
RAW_DIR = PACKAGE_DIR / "data" / "raw"

# Base URL of the UniLU course portal
BASE_URL = "https://portal.unilu.ch"

# URL of the search page where courses are listed
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

    # Parameters that are sent to the search page (semester filter)
    params = {"Semester": semester}

    # Send GET request to the search page
    resp = requests.get(SEARCH_URL, params=params, timeout=30)

    # Stop the program if the request failed
    resp.raise_for_status()

    # Parse the HTML response
    soup = BeautifulSoup(resp.text, "html.parser")

    # This list will store all found course IDs and URLs
    links: List[Tuple[str, str]] = []

    # IMPORTANT:
    # The links are relative and look like "details?code=FS261403"
    for a in soup.select("a[href^='details?code=']"):
        href = a.get("href")

        # Skip links without href attribute
        if not href:
            continue

        # Extract the course ID from the URL
        course_id = href.split("code=")[-1].strip()

        # Build the full URL to the course detail page
        detail_url = urljoin(BASE_URL + "/", href)

        # Only add valid course IDs
        if course_id:
            links.append((course_id, detail_url))

    # Remove duplicates and sort the list for stable output
    return sorted(set(links))


def scrape_semester(
    semester: str,
    refresh: bool = False,
    sleep_seconds: float = 0.2,
) -> None:
    """
    Scrape all course detail pages for one semester and cache them as HTML.
    """

    # Make sure the raw data directory exists
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Scraping semester: {semester}")

    # Fetch all course links for the given semester
    courses = _fetch_course_links(semester)

    print(f"Found {len(courses)} courses")

    # Loop over all courses
    for course_id, url in courses:
        # File where the HTML page will be saved
        out_file = RAW_DIR / f"{course_id}.html"

        # Skip download if file already exists and refresh is not enabled
        if out_file.exists() and not refresh:
            print(f"SKIP  {course_id}")
            continue

        print(f"FETCH {course_id}")

        # Download the course detail page
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()

        # Save HTML content to file
        out_file.write_text(resp.text, encoding="utf-8")

        # Sleep a bit to avoid sending too many requests at once
        time.sleep(sleep_seconds)

    print("Scraping finished.")


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    # Create argument parser for command line usage
    p = argparse.ArgumentParser(
        prog="myschedule.scrape",
        description="Scrape UniLU course pages (cache HTML)"
    )

    # Semester argument (e.g. FS26 or HS25)
    p.add_argument(
        "--semester",
        "-s",
        type=str,
        default="FS26",
        help="Semester code (e.g., FS26, HS25)"
    )

    # If set, existing HTML files will be overwritten
    p.add_argument(
        "--refresh",
        action="store_true",
        help="Re-fetch and overwrite existing HTML files"
    )

    # Time to wait between requests
    p.add_argument(
        "--sleep",
        type=float,
        default=0.2,
        help="Sleep seconds between requests"
    )

    return p


def main(argv: list[str] | None = None) -> None:
    # Parse command line arguments
    args = build_parser().parse_args(argv)

    # Start scraping with provided arguments
    scrape_semester(
        args.semester.strip(),
        refresh=args.refresh,
        sleep_seconds=args.sleep
    )


# This block runs only when the script is executed directly
if __name__ == "__main__":
    main()
