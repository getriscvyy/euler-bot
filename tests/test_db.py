"""Offline DB tests (no Discord needed). Run from the project root:

    python -m tests.test_db
"""
import asyncio
import os
from datetime import datetime, timedelta

import aiosqlite

from euler import config
from euler.db import database
from euler.utils import parse_time

T = config.DB_TEST


async def main():
    if os.path.exists(T):
        os.remove(T)   # fresh DB every run, so reruns don't pile up rows

    await database.init_db(T)

    # meetings
    mid = await database.add_meeting("Number Sense", "2026-09-15T15:30:00", "T-19", T)
    assert len(await database.list_meetings(T)) == 1
    assert await database.reschedule_meeting(mid, "2026-09-16T15:30:00", T) == 1
    assert await database.reschedule_meeting(999, "2026-09-16T15:30:00", T) == 0
    assert await database.delete_meeting(mid, T) == 1
    assert await database.delete_meeting(mid, T) == 0

    # reminders
    soon = (datetime.now() + timedelta(minutes=30)).isoformat(timespec="seconds")
    mid = await database.add_meeting("General Science", soon, "T-20", T)
    assert len(await database.get_due_meetings(60, T)) == 1
    await database.mark_reminded(mid, T)
    assert len(await database.get_due_meetings(60, T)) == 0

    # contests: one category entry per signup, multiple categories per user
    cid = await database.create_contest("Regionals", "2026-11-01T09:00:00", "Gym", T)
    assert await database.get_contest(cid, path=T) == (
        cid,
        "Regionals",
        "2026-11-01T09:00:00",
        "Gym",
    )
    assert await database.get_contest(999, path=T) is None
    assert await database.signup_contest(cid, 111, "General Mathematics", T) == "ok"
    assert await database.signup_contest(cid, 111, "General Mathematics", T) == "already"
    assert await database.signup_contest(cid, 111, "Number Sense", T) == "ok"
    assert await database.signup_contest(cid, 111, "Not a category", T) == "bad_category"
    assert await database.signup_contest(999, 111, "General Mathematics", T) == "no_contest"
    assert await database.get_roster(cid, path=T) == [
        (111, "General Mathematics"),
        (111, "Number Sense"),
    ]
    assert await database.get_roster(cid, category="General Mathematics", path=T) == [
        (111, "General Mathematics")
    ]
    counts = await database.get_contest_signup_counts(T)
    assert (cid, "General Mathematics", 1) in counts
    assert (cid, "Number Sense", 1) in counts
    assert (await database.list_contests(T))[0][4] == 2
    assert await database.withdraw_contest(cid, 111, "General Mathematics", T) == 1
    assert await database.withdraw_contest(cid, 111, "General Mathematics", T) == 0
    assert await database.get_roster(cid, category="General Mathematics", path=T) == []
    assert await database.withdraw_contest(cid, 111, path=T) == 1
    assert await database.withdraw_contest(cid, 111, path=T) == 0

    # old generic signups are migrated to category-aware rows
    legacy = os.path.join(config.DB_DIR, "test_legacy.sql")
    if os.path.exists(legacy):
        os.remove(legacy)
    async with aiosqlite.connect(legacy) as raw:
        await raw.execute("""
            CREATE TABLE contests (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                contest_date TEXT,
                location TEXT
            )
        """)
        await raw.execute(
            "INSERT INTO contests (id, name, contest_date, location) "
            "VALUES (1, 'Legacy', '2026-12-01T09:00:00', 'Room')"
        )
        await raw.execute("""
            CREATE TABLE signups (
                contest_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY (contest_id, user_id)
            )
        """)
        await raw.execute("INSERT INTO signups (contest_id, user_id) VALUES (1, 222)")
        await raw.commit()

    await database.init_db(legacy)
    assert await database.get_roster(1, path=legacy) == [(222, None)]
    assert await database.signup_contest(1, 222, "General Mathematics", legacy) == "ok"
    assert set(await database.get_roster(1, path=legacy)) == {
        (222, None),
        (222, "General Mathematics"),
    }
    os.remove(legacy)

    # reaction-role panel mappings
    await database.replace_role_panel(1, 2, 300, [("🔢", 111), ("➗", 222)], T)
    assert await database.get_role_panel(1, path=T) == (2, 300)
    assert await database.get_reaction_role(300, "🔢", T) == 111
    assert await database.get_reaction_role(300, "❓", T) is None
    await database.replace_role_panel(1, 2, 301, [("🔬", 333)], T)
    assert await database.get_role_panel(1, path=T) == (2, 301)
    assert await database.get_reaction_role(300, "🔢", T) is None
    assert await database.get_reaction_role(301, "🔬", T) == 333

    # parse_time
    assert parse_time("2026-09-15 15:30") == "2026-09-15T15:30:00"
    assert parse_time("tomorrow at 3") is None

    print("all good")


asyncio.run(main())
