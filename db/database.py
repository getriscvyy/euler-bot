from datetime import datetime, timedelta
import aiosqlite
import config

async def init_db(path=config.DB_PROD):
    async with aiosqlite.connect(path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY,
                category TEXT CHECK(category IN ('Number Sense', 'General Mathematics', 'Calculator Applications', 'General Science')),
                start_time TEXT,
                location TEXT,
                reminded INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS contests (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                contest_date TEXT,
                location TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS signups (
                contest_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY (contest_id, user_id)
            )
        """)
        await db.commit()

async def add_meeting(category, start_time, location, path=config.DB_PROD):
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(
            "INSERT INTO meetings (category, start_time, location) VALUES (?, ?, ?)",
            (category, start_time, location),
        )
        await db.commit()
        return cursor.lastrowid


async def list_meetings(path=config.DB_PROD):
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute("SELECT * FROM meetings")
        return await cursor.fetchall()


async def reschedule_meeting(meeting_id, new_start_time, path=config.DB_PROD):
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(
            "UPDATE meetings SET start_time = ?, reminded = 0 WHERE id = ?",
            (new_start_time, meeting_id),
        )
        await db.commit()
        return cursor.rowcount


async def delete_meeting(meeting_id, path=config.DB_PROD):
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
        await db.commit()
        return cursor.rowcount


async def get_due_meetings(lead_minutes, path=config.DB_PROD):
    """Not-yet-reminded meetings starting within the next `lead_minutes`."""
    now = datetime.now()
    start = now.isoformat(timespec="seconds")
    end = (now + timedelta(minutes=lead_minutes)).isoformat(timespec="seconds")
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(
            "SELECT id, category, start_time, location FROM meetings "
            "WHERE reminded = 0 AND start_time > ? AND start_time <= ?",
            (start, end),
        )
        return await cursor.fetchall()


async def mark_reminded(meeting_id, path=config.DB_PROD):
    async with aiosqlite.connect(path) as db:
        await db.execute("UPDATE meetings SET reminded = 1 WHERE id = ?", (meeting_id,))
        await db.commit()

async def create_contest(name, contest_date, location, path=config.DB_PROD):
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(
            "INSERT INTO contests (name, contest_date, location) VALUES (?, ?, ?)",
            (name, contest_date, location),
        )
        await db.commit()
        return cursor.lastrowid


async def list_contests(path=config.DB_PROD):
    """Rows: (id, name, contest_date, location, signup_count)"""
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute("""
            SELECT c.id, c.name, c.contest_date, c.location, COUNT(s.user_id)
            FROM contests c LEFT JOIN signups s ON s.contest_id = c.id
            GROUP BY c.id
            ORDER BY c.contest_date
        """)
        return await cursor.fetchall()


async def signup_contest(contest_id, user_id, path=config.DB_PROD):
    """Returns 'ok', 'no_contest', or 'already'."""
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute("SELECT 1 FROM contests WHERE id = ?", (contest_id,))
        if await cursor.fetchone() is None:
            return "no_contest"
        try:
            await db.execute(
                "INSERT INTO signups (contest_id, user_id) VALUES (?, ?)",
                (contest_id, user_id),
            )
            await db.commit()
        except aiosqlite.IntegrityError:
            return "already"
        return "ok"


async def withdraw_contest(contest_id, user_id, path=config.DB_PROD):
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(
            "DELETE FROM signups WHERE contest_id = ? AND user_id = ?",
            (contest_id, user_id),
        )
        await db.commit()
        return cursor.rowcount


async def get_roster(contest_id, path=config.DB_PROD):
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(
            "SELECT user_id FROM signups WHERE contest_id = ?", (contest_id,)
        )
        return [row[0] for row in await cursor.fetchall()]
