import os

from dotenv import load_dotenv

from euler.constants import CATEGORIES

# euler/config.py -> euler/ -> project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(BASE_DIR, ".env"))

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
OFFICER_ROLE_ID = int(os.getenv("OFFICER_ROLE_ID", "0"))
REMINDER_CHANNEL_ID = int(os.getenv("REMINDER_CHANNEL_ID", "0"))
ANNOUNCEMENTS_CHANNEL_ID = int(os.getenv("ANNOUNCEMENTS_CHANNEL_ID", "0"))


def _category_role_id(category):
    env_name = f"{category.upper().replace(' ', '_')}_ROLE_ID"
    return int(os.getenv(env_name, "0"))


# Existing Discord roles pinged for reminders in each category.
CATEGORY_ROLE_IDS = {
    category: _category_role_id(category) for category in CATEGORIES
}

REMINDER_LEAD_MINUTES = 60
REMINDER_CHECK_MINUTES = 1

DB_DIR = os.path.join(BASE_DIR, "db")
DB_PROD = os.path.join(DB_DIR, "meetings.sql")
DB_TEST = os.path.join(DB_DIR, "test.sql")
