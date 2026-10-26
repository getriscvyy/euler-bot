from datetime import datetime

from euler import config

TIME_FORMAT = "%Y-%m-%d %H:%M"   # what users type, e.g. 2026-09-15 15:30


def parse_time(text):
    """User text -> naive ISO 8601 string for the DB, or None if malformed.

    Times are interpreted as club-local wall time in config.TIMEZONE.
    """
    try:
        return datetime.strptime(text, TIME_FORMAT).isoformat(timespec="seconds")
    except ValueError:
        return None


def local_now():
    """Current time as an aware datetime in the club timezone."""
    return datetime.now(config.TIMEZONE)


def local_now_naive():
    """Current club-local time without tzinfo, matching naive DB timestamps."""
    return local_now().replace(tzinfo=None)


def local_now_iso():
    """Current club-local time as the ISO string format stored in SQLite."""
    return local_now_naive().isoformat(timespec="seconds")
