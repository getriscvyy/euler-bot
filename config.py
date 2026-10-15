import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
OFFICER_ROLE_ID = int(os.getenv("OFFICER_ROLE_ID", "0"))
MEMBER_ROLE_ID = int(os.getenv("MEMBER_ROLE_ID", "0"))
REMINDER_CHANNEL_ID = int(os.getenv("REMINDER_CHANNEL_ID", "0"))

REMINDER_LEAD_MINUTES = 60
REMINDER_CHECK_MINUTES = 1

DB_PROD = os.path.join(BASE_DIR, "db", "meetings.sql")
DB_TEST = os.path.join(BASE_DIR, "db", "test.sql")
