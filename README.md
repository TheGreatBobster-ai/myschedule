# MySchedule — Personal University Timetable Manager

MySchedule is an interactive Python application that automatically builds a personal university timetable by scraping the University of Lucerne course catalog.

It allows students to:

- Search and select courses
- Detect timetable conflicts
- View weekly timetables and full agendas
- Export schedules to calendar apps (Google, Outlook, iOS)

The tool combines web scraping, data processing, and a rich interactive terminal interface.

_________________________________________________________________

# Features

- Automatic scraping of UniLU course catalog
- Intelligent course search by title, code, or instructor
- Persistent personal course selection
- Conflict detection between overlapping events
- Weekly timetable visualization
- Chronological agenda view
- Export to .ics calendar file
- Cross-platform (Windows, macOS, Linux)

_________________________________________________________________

# Installation

1) Clone the repository:

git clone https://github.com/TheGreatBobster-ai/myschedule.git
cd myschedule

2) Create and activate a virtual environment:

python -m venv .venv
source .venv/bin/activate      # macOS/Linux
.venv\Scripts\activate         # Windows

3) Install dependencies:

pip install -r requirements.txt

-----------------------------------------------------------------

## Optional: Install as system command

You can install MySchedule as a system-wide command:

pip install -e .


-> After that, you can start the program from anywhere using:

myschedule


Instead of:

python -m myschedule

_________________________________________________________________

# First Start (Important)

On the very first run, no course data exists yet.

->Start the application:

python -m myschedule


-> The program will automatically detect that no data is available and guide you to download the course catalog.

Simply follow the on-screen instructions.

_________________________________________________________________

# Normal Usage

Start the interactive application:

python -m myschedule


Main workflow:

1) Update data (once per semester)
2) Search & add courses
3) View timetable / agenda
4) Check conflicts
5) Export to calendar

All functions are accessible via the interactive menu.

_________________________________________________________________

# Updating Course Data

To refresh all course information:

python -m myschedule


-> Select:

[8] Update data (re-scrape UniLU)


This downloads the latest course catalog and rebuilds the internal database.

_________________________________________________________________

# Calendar Export

MySchedule can export your personal timetable to a calendar file:

- Google Calendar
- Outlook
- Apple Calendar

The exported .ics file can be imported into any standard calendar application.
Apple calenders on phones can be tricky but should work when the file is opened
in one's mail-app on the phone.

_________________________________________________________________

# Technical Overview

Architecture:

scrape.py   → downloads raw HTML
parse.py    → converts HTML to structured JSON
interactive.py → user interface
conflicts.py → overlap detection
export_ics.py → calendar export


All user selections are stored locally and persist across sessions.

_________________________________________________________________

# Project Context

This project was developed as part of the Introductory Computer Science & Programming course.

It demonstrates:

- Modular software architecture
- Web scraping
- Data processing pipelines
- Interactive terminal UI design
- Collaborative software development

_________________________________________________________________

# Authors

Developed by:

Niklas & Robert

University of Lucerne