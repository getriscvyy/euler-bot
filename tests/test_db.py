"""Offline DB tests (no Discord needed). Run from the project root:

    python -m tests.test_db
"""
import asyncio
import os
from datetime import timedelta

import aiosqlite

from euler import config
from euler.db import database
from euler.utils import local_now, local_now_naive, parse_time

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
    soon = (local_now_naive() + timedelta(minutes=30)).isoformat(
        timespec="seconds"
    )
    mid = await database.add_meeting("General Science", soon, "T-20", T)
    assert len(await database.get_due_meetings(60, T)) == 1
    await database.mark_reminded(mid, T)
    assert len(await database.get_due_meetings(60, T)) == 0

    # contests: one category entry per signup, multiple categories per user
    contest_start = (local_now_naive() + timedelta(days=30)).isoformat(
        timespec="seconds"
    )
    cid = await database.create_contest("Regionals", contest_start, "Gym", path=T)
    assert await database.get_contest(cid, path=T) == (
        cid,
        "Regionals",
        contest_start,
        "Gym",
        None,
        0,
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
    assert (await database.list_contests(T))[0][5] == 2
    assert await database.withdraw_contest(cid, 111, "General Mathematics", T) == 1
    assert await database.withdraw_contest(cid, 111, "General Mathematics", T) == 0
    assert await database.get_roster(cid, category="General Mathematics", path=T) == []
    assert await database.withdraw_contest(cid, 111, path=T) == 1
    assert await database.withdraw_contest(cid, 111, path=T) == 0

    # one-shot multi-category signup
    multi_start = (local_now_naive() + timedelta(days=20)).isoformat(
        timespec="seconds"
    )
    multi_cid = await database.create_contest(
        "Invitational", multi_start, "Hall", path=T
    )
    changes = await database.update_contest_signups(
        multi_cid,
        333,
        {
            "Number Sense": True,
            "General Mathematics": True,
            "Calculator Applications": False,
            "General Science": False,
        },
        T,
    )
    assert set(changes) == {
        ("added", "Number Sense"),
        ("added", "General Mathematics"),
    }
    assert set(await database.get_roster(multi_cid, path=T)) == {
        (333, "Number Sense"),
        (333, "General Mathematics"),
    }

    changes = await database.update_contest_signups(
        multi_cid,
        333,
        {"Number Sense": False, "General Science": True},
        T,
    )
    assert set(changes) == {
        ("removed", "Number Sense"),
        ("added", "General Science"),
    }
    assert set(await database.get_roster(multi_cid, path=T)) == {
        (333, "General Mathematics"),
        (333, "General Science"),
    }
    assert await database.update_contest_signups(
        multi_cid, 333, {"Not a category": True}, T
    ) == "bad_category"
    assert await database.update_contest_signups(
        999, 333, {"Number Sense": True}, T
    ) == "no_contest"

    # deleting a contest also deletes its signups
    assert await database.delete_contest(multi_cid, T) == 1
    assert await database.get_contest(multi_cid, path=T) is None
    assert await database.get_roster(multi_cid, path=T) == []
    assert await database.delete_contest(multi_cid, T) == 0

    # signup deadlines close both single and multi-category signup paths
    future_contest = (local_now_naive() + timedelta(days=60)).isoformat(
        timespec="seconds"
    )
    past_deadline = (local_now_naive() - timedelta(minutes=1)).isoformat(
        timespec="seconds"
    )
    deadline_cid = await database.create_contest(
        "Closed Contest",
        future_contest,
        "Room",
        signup_deadline=past_deadline,
        path=T,
    )
    assert await database.signup_contest(
        deadline_cid, 444, "Number Sense", T
    ) == "closed"
    assert await database.update_contest_signups(
        deadline_cid, 444, {"General Science": True}, T
    ) == "closed"
    assert await database.get_roster(deadline_cid, path=T) == []
    assert await database.update_contest_deadline(deadline_cid, None, T) == 1
    assert await database.signup_contest(
        deadline_cid, 444, "Number Sense", T
    ) == "ok"

    # contest reminders use the same one-hour lead window as meetings
    reminder_start = (local_now_naive() + timedelta(minutes=30)).isoformat(
        timespec="seconds"
    )
    reminder_cid = await database.create_contest(
        "Reminder Contest", reminder_start, "Room", path=T
    )
    await database.update_contest_signups(
        reminder_cid, 555, {"General Mathematics": True}, T
    )
    due_contests = await database.get_due_contests(60, T)
    assert [row[0] for row in due_contests] == [reminder_cid]
    await database.mark_contest_reminded(reminder_cid, T)
    assert await database.get_due_contests(60, T) == []
    assert await database.delete_contest(deadline_cid, T) == 1
    assert await database.delete_contest(reminder_cid, T) == 1

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
    assert (await database.get_contest(1, path=legacy))[4:] == (None, 0)
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

    # parse_time and club timezone
    assert parse_time("2026-09-15 15:30") == "2026-09-15T15:30:00"
    assert parse_time("tomorrow at 3") is None
    now = local_now()
    assert now.tzinfo is not None
    assert str(now.tzinfo) == config.TIMEZONE_NAME

    print("all good")


asyncio.run(main())
