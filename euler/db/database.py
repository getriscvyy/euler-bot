import os
from datetime import timedelta

import aiosqlite

from euler import config
from euler.constants import CATEGORIES
from euler.utils import local_now_iso, local_now_naive

_CATEGORY_VALUES = ", ".join(f"'{category}'" for category in CATEGORIES)

_SIGNUPS_TABLE_SQL = f"""
    CREATE TABLE IF NOT EXISTS signups (
        contest_id INTEGER,
        user_id INTEGER,
        category TEXT CHECK(category IS NULL OR category IN ({_CATEGORY_VALUES})),
        PRIMARY KEY (contest_id, user_id, category)
    )
"""


async def _ensure_signups_schema(db):
    """Create the category-aware signups table, migrating the old per-contest table."""
    cursor = await db.execute("PRAGMA table_info(signups)")
    columns = await cursor.fetchall()
    if not columns:
        await db.execute(_SIGNUPS_TABLE_SQL)
        return

    column_names = {column[1] for column in columns}
    primary_key = [
        column[1] for column in sorted(columns, key=lambda column: column[5]) if column[5]
    ]
    if "category" in column_names and primary_key == ["contest_id", "user_id", "category"]:
        return

    # Old signups were one generic entry per user. Preserve them with a NULL
    # category so they show as "Unspecified" until people re-sign up.
    has_category = "category" in column_names
    await db.commit()
    await db.execute("BEGIN IMMEDIATE")
    try:
        await db.execute("ALTER TABLE signups RENAME TO signups_legacy")
        await db.execute(_SIGNUPS_TABLE_SQL)
        category_value = "category" if has_category else "NULL"
        await db.execute(
            "INSERT INTO signups (contest_id, user_id, category) "
            f"SELECT contest_id, user_id, {category_value} FROM signups_legacy"
        )
        await db.execute("DROP TABLE signups_legacy")
    except Exception:
        await db.rollback()
        raise
    await db.commit()


async def _ensure_contests_schema(db):
    """Add columns introduced after the original contests table."""
    cursor = await db.execute("PRAGMA table_info(contests)")
    columns = {column[1] for column in await cursor.fetchall()}
    if "signup_deadline" not in columns:
        await db.execute("ALTER TABLE contests ADD COLUMN signup_deadline TEXT")
    if "reminded" not in columns:
        await db.execute(
            "ALTER TABLE contests ADD COLUMN reminded INTEGER DEFAULT 0"
        )


async def init_db(path=config.DB_PROD):
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    async with aiosqlite.connect(path) as db:
        await db.execute(f"""
            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY,
                category TEXT CHECK(category IN ({_CATEGORY_VALUES})),
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
                location TEXT,
                signup_deadline TEXT,
                reminded INTEGER DEFAULT 0
            )
        """)
        await _ensure_contests_schema(db)
        await _ensure_signups_schema(db)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS role_panels (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reaction_roles (
                guild_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                emoji TEXT NOT NULL,
                role_id INTEGER NOT NULL,
                PRIMARY KEY (message_id, emoji)
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
    now = local_now_naive()
    start = now.isoformat(timespec="seconds")
    end = (now + timedelta(minutes=lead_minutes)).isoformat(timespec="seconds")
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(
            "SELECT id, category, start_time, location FROM meetings "
            "WHERE reminded = 0 AND start_time > ? AND start_time <= ? "
            "ORDER BY start_time",
            (start, end),
        )
        return await cursor.fetchall()


async def mark_reminded(meeting_id, path=config.DB_PROD):
    async with aiosqlite.connect(path) as db:
        await db.execute("UPDATE meetings SET reminded = 1 WHERE id = ?", (meeting_id,))
        await db.commit()


async def create_contest(
    name, contest_date, location, signup_deadline=None, path=config.DB_PROD
):
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(
            "INSERT INTO contests (name, contest_date, location, signup_deadline) "
            "VALUES (?, ?, ?, ?)",
            (name, contest_date, location, signup_deadline),
        )
        await db.commit()
        return cursor.lastrowid


async def get_contest(contest_id, path=config.DB_PROD):
    """Row: (id, name, contest_date, location, signup_deadline, reminded)."""
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(
            "SELECT id, name, contest_date, location, signup_deadline, reminded "
            "FROM contests WHERE id = ?",
            (contest_id,),
        )
        return await cursor.fetchone()


async def delete_contest(contest_id, path=config.DB_PROD):
    """Delete a contest and all of its signups. Returns contests deleted (0 or 1)."""
    async with aiosqlite.connect(path) as db:
        await db.execute("DELETE FROM signups WHERE contest_id = ?", (contest_id,))
        cursor = await db.execute("DELETE FROM contests WHERE id = ?", (contest_id,))
        await db.commit()
        return cursor.rowcount


async def list_contests(path=config.DB_PROD):
    """Rows: (id, name, contest_date, location, signup_deadline, signup_count).

    signup_count is the number of subcontest entries, so one person signed up
    for two categories counts twice.
    """
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute("""
            SELECT c.id, c.name, c.contest_date, c.location, c.signup_deadline,
                   COUNT(s.user_id)
            FROM contests c LEFT JOIN signups s ON s.contest_id = c.id
            GROUP BY c.id
            ORDER BY c.contest_date
        """)
        return await cursor.fetchall()


async def update_contest_deadline(contest_id, deadline, path=config.DB_PROD):
    """Set or clear (deadline=None) a contest's signup deadline."""
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(
            "UPDATE contests SET signup_deadline = ? WHERE id = ?",
            (deadline, contest_id),
        )
        await db.commit()
        return cursor.rowcount


async def get_due_contests(lead_minutes, path=config.DB_PROD):
    """Not-yet-reminded contests starting within the next `lead_minutes`."""
    now = local_now_naive()
    start = now.isoformat(timespec="seconds")
    end = (now + timedelta(minutes=lead_minutes)).isoformat(timespec="seconds")
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(
            "SELECT id, name, contest_date, location FROM contests "
            "WHERE reminded = 0 AND contest_date > ? AND contest_date <= ? "
            "ORDER BY contest_date",
            (start, end),
        )
        return await cursor.fetchall()


async def mark_contest_reminded(contest_id, path=config.DB_PROD):
    async with aiosqlite.connect(path) as db:
        await db.execute(
            "UPDATE contests SET reminded = 1 WHERE id = ?", (contest_id,)
        )
        await db.commit()


async def get_contest_signup_counts(path=config.DB_PROD):
    """Rows: (contest_id, category, count), including legacy NULL categories."""
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(
            "SELECT contest_id, category, COUNT(*) FROM signups "
            "GROUP BY contest_id, category"
        )
        return await cursor.fetchall()


async def signup_contest(contest_id, user_id, category, path=config.DB_PROD):
    """Returns 'ok', 'no_contest', 'already', 'closed', or 'bad_category'."""
    if category not in CATEGORIES:
        return "bad_category"
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(
            "SELECT signup_deadline FROM contests WHERE id = ?", (contest_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return "no_contest"
        if row[0] is not None and local_now_iso() >= row[0]:
            return "closed"
        try:
            await db.execute(
                "INSERT INTO signups (contest_id, user_id, category) VALUES (?, ?, ?)",
                (contest_id, user_id, category),
            )
            await db.commit()
        except aiosqlite.IntegrityError:
            return "already"
        return "ok"


async def update_contest_signups(
    contest_id, user_id, selections, path=config.DB_PROD
):
    """Apply a member's category choices in one transaction.

    `selections` maps category -> bool. True signs up, False withdraws, and
    categories not present are left unchanged. Returns 'no_contest',
    'bad_category', 'closed', or a list of ('added'|'removed', category) changes.
    """
    if any(category not in CATEGORIES for category in selections):
        return "bad_category"

    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(
            "SELECT signup_deadline FROM contests WHERE id = ?", (contest_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return "no_contest"
        if row[0] is not None and local_now_iso() >= row[0]:
            return "closed"

        changes = []
        for category, wanted in selections.items():
            if wanted:
                cursor = await db.execute(
                    "INSERT OR IGNORE INTO signups (contest_id, user_id, category) "
                    "VALUES (?, ?, ?)",
                    (contest_id, user_id, category),
                )
                if cursor.rowcount:
                    changes.append(("added", category))
            else:
                cursor = await db.execute(
                    "DELETE FROM signups "
                    "WHERE contest_id = ? AND user_id = ? AND category = ?",
                    (contest_id, user_id, category),
                )
                if cursor.rowcount:
                    changes.append(("removed", category))
        await db.commit()
        return changes


async def withdraw_contest(contest_id, user_id, category=None, path=config.DB_PROD):
    """Remove one category signup, or every category when category is None."""
    async with aiosqlite.connect(path) as db:
        if category is None:
            cursor = await db.execute(
                "DELETE FROM signups WHERE contest_id = ? AND user_id = ?",
                (contest_id, user_id),
            )
        else:
            cursor = await db.execute(
                "DELETE FROM signups WHERE contest_id = ? AND user_id = ? AND category = ?",
                (contest_id, user_id, category),
            )
        await db.commit()
        return cursor.rowcount


async def get_roster(contest_id, category=None, path=config.DB_PROD):
    """Rows: (user_id, category), optionally limited to one category."""
    async with aiosqlite.connect(path) as db:
        if category is None:
            cursor = await db.execute(
                "SELECT user_id, category FROM signups WHERE contest_id = ? "
                "ORDER BY category, user_id",
                (contest_id,),
            )
        else:
            cursor = await db.execute(
                "SELECT user_id, category FROM signups WHERE contest_id = ? AND category = ? "
                "ORDER BY user_id",
                (contest_id, category),
            )
        return await cursor.fetchall()


async def get_role_panel(guild_id, path=config.DB_PROD):
    """Row: (channel_id, message_id), or None if the guild has no panel."""
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(
            "SELECT channel_id, message_id FROM role_panels WHERE guild_id = ?",
            (guild_id,),
        )
        return await cursor.fetchone()


async def replace_role_panel(
    guild_id, channel_id, message_id, mappings, path=config.DB_PROD
):
    """Save the current panel and its (emoji, role_id) reaction mappings."""
    mappings = list(mappings)
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(
            "SELECT message_id FROM role_panels WHERE guild_id = ?", (guild_id,)
        )
        old_panel = await cursor.fetchone()
        if old_panel is not None:
            await db.execute(
                "DELETE FROM reaction_roles WHERE message_id = ?", (old_panel[0],)
            )

        await db.execute(
            """
            INSERT INTO role_panels (guild_id, channel_id, message_id)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                channel_id = excluded.channel_id,
                message_id = excluded.message_id
            """,
            (guild_id, channel_id, message_id),
        )
        if mappings:
            await db.executemany(
                "INSERT INTO reaction_roles (guild_id, message_id, emoji, role_id) "
                "VALUES (?, ?, ?, ?)",
                [
                    (guild_id, message_id, emoji, role_id)
                    for emoji, role_id in mappings
                ],
            )
        await db.commit()


async def get_reaction_role(message_id, emoji, path=config.DB_PROD):
    """Role ID mapped to a reaction on a panel message, or None."""
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(
            "SELECT role_id FROM reaction_roles WHERE message_id = ? AND emoji = ?",
            (message_id, emoji),
        )
        row = await cursor.fetchone()
        return row[0] if row is not None else None
