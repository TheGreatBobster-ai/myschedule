# Python Package Template

This is a template for the Python project in the course _Introduction to Computer Science and Programming_ at the University of Lucerne.

## Prepare Repository
1. Rename all instances of `"project_name"`
2. Create virtual environment: `python -m venv venv`
3. Activate virtual environment:
	- MacOS/Linux: `source venv/bin/activate`
    - Windows: `venv\Scripts\activate`
4. Install requirements and requirements-test:
	- `pip install -r requirements.txt -r requirements-test.txt`
5. Run tests `pytest tests/test_cli.py`
6. Run project
    - `python -m myschedule` or
	- `python myschedule/__main__.py`
		- `__main__.py` is the entry point
7. Run code linting: `pylint [myschedule]`
8. Run static type checking: `mypy .`
9. Run code formatter: `black .`


#####

# UniLu MySchedule (CLI)

A local Python CLI tool that scrapes the public university course catalog,
allows students to search and select courses, detects schedule conflicts,
and exports the schedule as an iCalendar (.ics) file.

## Features
- Scrape public course pages (cached locally)
- Parse course metadata and all individual event dates
- Search courses by keyword
- Select / remove courses
- Detect schedule conflicts
- Export calendar (.ics)

## Setup (Windows, VS Code)
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-test.txt
pip install -e .
