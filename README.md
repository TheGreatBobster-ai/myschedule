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
    - `python -m project_name` or
	- `python project_name/__main__.py`
		- `__main__.py` is the entry point
7. Run code linting: `pylint [project_name]`
8. Run static type checking: `mypy .`
9. Run code formatter: `black .`
