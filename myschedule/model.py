"""
Data model definitions.

We define the structure of Course and Event here so:
- all modules agree on the same fields
- the code stays readable for beginners
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class Course:
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
    event_id: str
    course_id: str
    title: str
    kind: str
    date: str
    start: str
    end: str
    location: str
    note: Optional[str]
