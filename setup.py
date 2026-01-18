from __future__ import annotations

from pathlib import Path
from typing import Any

from setuptools import find_packages, setup


ROOT = Path(__file__).resolve().parent


def read_text(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return default


def read_requirements(filename: str) -> list[str]:
    req_path = ROOT / filename
    if not req_path.exists():
        return []
    lines = read_text(req_path).splitlines()
    out: list[str] = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-r"):
            continue
        out.append(line)
    return out


version = read_text(ROOT / "myschedule" / "VERSION", default="0.1.0")

setup(
    name="myschedule",
    version=version,
    description="MySchedule – UniLU course scraper + timetable manager (CLI + interactive)",
    url="https://github.com/TheGreatBobster-ai/myschedule.git",
    long_description=read_text(ROOT / "README.md"),
    long_description_content_type="text/markdown",
    author="Robert Puselja / Nikolas Kehrer",
    packages=find_packages(exclude=("tests", ".github")),
    install_requires=read_requirements("requirements.txt"),
    extras_require={"dev": read_requirements("requirements-dev.txt")},
    entry_points={"console_scripts": ["myschedule=myschedule.cli:main"]},
)
