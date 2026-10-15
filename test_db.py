"""Offline DB tests (no Discord needed). Run from project root: python -m test_db"""
import asyncio
import os
from datetime import datetime, timedelta

import config
from db import database
from utils import parse_time

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

    # contests
    cid = await database.create_contest("Regionals", "2026-11-01T09:00:00", "Gym", T)
    assert await database.signup_contest(cid, 111, T) == "ok"
    assert await database.signup_contest(cid, 111, T) == "already"
    assert await database.signup_contest(999, 111, T) == "no_contest"
    assert await database.get_roster(cid, T) == [111]
    assert (await database.list_contests(T))[0][4] == 1
    assert await database.withdraw_contest(cid, 111, T) == 1
    assert await database.withdraw_contest(cid, 111, T) == 0

    # parse_time
    assert parse_time("2026-09-15 15:30") == "2026-09-15T15:30:00"
    assert parse_time("tomorrow at 3") is None

    print("all good")


asyncio.run(main())
