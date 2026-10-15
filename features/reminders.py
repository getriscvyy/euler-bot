import asyncio
import logging

import discord
from discord.ext import tasks

import config
from bot_instance import client
from db import database

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


async def send_due_reminders():
    due = await database.get_due_meetings(config.REMINDER_LEAD_MINUTES)
    if not due:
        return

    guild = client.get_guild(config.GUILD_ID)
    if guild is None:
        log.warning("Guild %s not found; skipping reminders", config.GUILD_ID)
        return

    role = guild.get_role(config.MEMBER_ROLE_ID)
    channel = guild.get_channel(config.REMINDER_CHANNEL_ID)
    recipients = [m for m in role.members if not m.bot] if role else []

    for meeting_id, category, start_time, location in due:
        when = start_time.replace("T", " ")
        text = f"Reminder: **{category}** meeting at {when} in {location}."

        failed = []
        for member in recipients:
            try:
                await member.send(text)
            except (discord.Forbidden, discord.HTTPException):   # DMs closed / blocked
                failed.append(member)
            await asyncio.sleep(0.5)   # stay friendly with rate limits

        # Channel fallback: ping whoever couldn't be DMed, or post once if there's no recipient list
        if channel is not None and (failed or not recipients):
            pings = " ".join(m.mention for m in failed)
            try:
                await channel.send(f"{text} {pings}".strip())
            except discord.HTTPException:
                log.warning("Could not post fallback reminder for meeting %s", meeting_id)

        await database.mark_reminded(meeting_id)
