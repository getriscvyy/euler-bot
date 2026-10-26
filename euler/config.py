import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

from euler.constants import CATEGORIES

# euler/config.py -> euler/ -> project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Optional alternate env file, useful for a separate dev/test bot:
#   EULER_ENV_FILE=.env.dev python -m main
env_file = os.path.expanduser(os.getenv("EULER_ENV_FILE", "").strip() or ".env")
if not os.path.isabs(env_file):
    env_file = os.path.join(BASE_DIR, env_file)
load_dotenv(env_file)


def _env_int(name, default=0):
    """Read an integer setting, treating a blank value like an omitted one."""
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value)


TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = _env_int("GUILD_ID")
OFFICER_ROLE_ID = _env_int("OFFICER_ROLE_ID")
REMINDER_CHANNEL_ID = _env_int("REMINDER_CHANNEL_ID")
ANNOUNCEMENTS_CHANNEL_ID = _env_int("ANNOUNCEMENTS_CHANNEL_ID")
REACTION_ROLES_CHANNEL_ID = _env_int("REACTION_ROLES_CHANNEL_ID")

TIMEZONE_NAME = os.getenv("TIMEZONE", "America/Chicago").strip() or "America/Chicago"
try:
    TIMEZONE = ZoneInfo(TIMEZONE_NAME)
except ZoneInfoNotFoundError as exc:
    raise RuntimeError(f"Invalid TIMEZONE {TIMEZONE_NAME!r}") from exc


def _category_role_id(category):
    env_name = f"{category.upper().replace(' ', '_')}_ROLE_ID"
    return _env_int(env_name)


# Existing Discord roles pinged for reminders in each category.
CATEGORY_ROLE_IDS = {
    category: _category_role_id(category) for category in CATEGORIES
}


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


DEV_MODE = _env_bool("DEV_MODE", False)

MEETING_REMINDER_LEAD_MINUTES = _env_int(
    "MEETING_REMINDER_LEAD_MINUTES", 10
)
CONTEST_REMINDER_LEAD_MINUTES = _env_int(
    "CONTEST_REMINDER_LEAD_MINUTES", 60
)
REMINDER_CHECK_MINUTES = 1

DB_DIR = os.path.join(BASE_DIR, "db")
DEFAULT_DB_PROD = os.path.join(DB_DIR, "meetings.sql")

_db_path = os.getenv("EULER_DB_PATH", "").strip()
if _db_path:
    if not os.path.isabs(_db_path):
        _db_path = os.path.join(BASE_DIR, _db_path)
    DB_PROD = os.path.abspath(_db_path)
else:
    DB_PROD = DEFAULT_DB_PROD

DB_TEST = os.path.join(DB_DIR, "test.sql")
