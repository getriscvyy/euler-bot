import logging

import discord
from discord.ext import tasks

from euler import config
from euler.bot_instance import client
from euler.constants import CATEGORIES
from euler.db import database

log = logging.getLogger(__name__)


@tasks.loop(minutes=config.REMINDER_CHECK_MINUTES)
async def reminder_loop():
    # Never let an exception kill the loop: this runs unattended on the Pi.
    try:
        await send_due_reminders()
    except Exception:
        log.exception("reminder loop iteration failed")


@reminder_loop.before_loop
async def before_reminder_loop():
    await client.wait_until_ready()   # guild/role/channel lookups need a ready client


def _meeting_text(meeting):
    _, category, start_time, location = meeting
    when = start_time.replace("T", " ")
    return f"Reminder: **{category}** meeting at {when} in {location}."


def _contest_reminder(guild, contest, signup_rows):
    _, name, contest_date, location = contest
    when = contest_date.replace("T", " ")

    # One reminder per contest, pinging only the roles for categories that
    # actually have signups.
    signed_categories = {
        category for _, category in signup_rows if category is not None
    }
    categories = [category for category in CATEGORIES if category in signed_categories]

    roles = []
    seen_role_ids = set()
    for category in categories:
        role_id = config.CATEGORY_ROLE_IDS.get(category, 0)
        role = guild.get_role(role_id) if role_id else None
        if role is not None and role.id not in seen_role_ids:
            roles.append(role)
            seen_role_ids.add(role.id)

    if roles:
        ping = " ".join(role.mention for role in roles) + " "
        allowed_mentions = discord.AllowedMentions(roles=roles)
    else:
        ping = ""
        allowed_mentions = discord.AllowedMentions.none()

    category_text = (
        f" Categories: {', '.join(categories)}." if categories else ""
    )
    text = (
        f"{ping}⏰ **Contest reminder:** **{name}** starts at {when} in "
        f"{location}.{category_text}"
    )
    return text, allowed_mentions


async def send_due_reminders():
    """Send all due meeting/contest reminders. Returns (meetings, contests)."""
    due_meetings = await database.get_due_meetings(config.REMINDER_LEAD_MINUTES)
    due_contests = await database.get_due_contests(config.REMINDER_LEAD_MINUTES)
    if not due_meetings and not due_contests:
        return 0, 0

    guild = client.get_guild(config.GUILD_ID)
    if guild is None:
        log.warning("Guild %s not found; skipping reminders", config.GUILD_ID)
        return 0, 0

    channel = guild.get_channel(config.REMINDER_CHANNEL_ID)
    if channel is None:
        log.warning(
            "Reminder channel %s not found; skipping reminders",
            config.REMINDER_CHANNEL_ID,
        )
        return 0, 0

    sent_meetings = 0
    for meeting in due_meetings:
        meeting_id, category, start_time, location = meeting

        role_id = config.CATEGORY_ROLE_IDS.get(category, 0)
        role = guild.get_role(role_id) if role_id else None
        if role is None:
            log.warning(
                "No notification role configured for category %s; posting without a ping",
                category,
            )
            ping = ""
            allowed_mentions = discord.AllowedMentions.none()
        else:
            ping = f"{role.mention} "
            allowed_mentions = discord.AllowedMentions(roles=[role])

        text = f"{ping}{_meeting_text(meeting)}"
        try:
            await channel.send(text, allowed_mentions=allowed_mentions)
        except discord.HTTPException:
            log.warning("Could not post reminder for meeting %s", meeting_id)
            continue

        await database.mark_reminded(meeting_id)
        sent_meetings += 1

    sent_contests = 0
    for contest in due_contests:
        contest_id = contest[0]
        signup_rows = await database.get_roster(contest_id)
        text, allowed_mentions = _contest_reminder(guild, contest, signup_rows)

        try:
            await channel.send(text, allowed_mentions=allowed_mentions)
        except discord.HTTPException:
            log.warning("Could not post reminder for contest %s", contest_id)
            continue

        await database.mark_contest_reminded(contest_id)
        sent_contests += 1

    return sent_meetings, sent_contests
