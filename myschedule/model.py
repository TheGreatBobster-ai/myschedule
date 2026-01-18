"""
Central data model definitions used across the project.

This module defines the canonical structure of Course and Event objects so that:
- all modules share the same field names
- data structures remain consistent across scraping, parsing and UI layers
- the code stays readable and beginner-friendly
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class Course:
    """
    Represents one university course as stored in courses.json.
    """

    course_id: str
    title: str
    semester: Optional[str]
    type: Optional[str]
    instructors: List[str]
    department: Optional[str]
    study_level: Optional[str]
    source_url: str


@dataclass
class Event:
    """
    Represents one concrete teaching event (single date & time slot).

    Each Event corresponds to exactly one line in the UniLU "Termin/e" field.
    """

    event_id: str
    course_id: str
    title: str
    kind: str
    date: str
    start: str
    end: str
    location: str
    note: Optional[str]
