"""
Package entry point.

Allows running the application via:

    python -m myschedule

This simply forwards execution to myschedule.cli.main().
"""

from myschedule.cli import main

if __name__ == "__main__":
    main()
