from datetime import datetime

TIME_FORMAT = "%Y-%m-%d %H:%M"   # what users type, e.g. 2026-09-15 15:30


def parse_time(text):
    """User text -> ISO 8601 string for the DB, or None if the format is wrong.
    Pure function: testable without Discord."""
    try:
        return datetime.strptime(text, TIME_FORMAT).isoformat()
    except ValueError:
        return None
