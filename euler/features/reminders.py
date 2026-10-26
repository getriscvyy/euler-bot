import logging

import discord
from discord.ext import tasks

from euler import config
from euler.bot_instance import client
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


async def send_due_reminders():
    due = await database.get_due_meetings(config.REMINDER_LEAD_MINUTES)
    if not due:
        return

    guild = client.get_guild(config.GUILD_ID)
    if guild is None:
        log.warning("Guild %s not found; skipping reminders", config.GUILD_ID)
        return

    channel = guild.get_channel(config.REMINDER_CHANNEL_ID)
    if channel is None:
        log.warning(
            "Reminder channel %s not found; skipping reminders",
            config.REMINDER_CHANNEL_ID,
        )
        return

    for meeting_id, category, start_time, location in due:
        when = start_time.replace("T", " ")

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

        text = f"{ping}Reminder: **{category}** meeting at {when} in {location}."
        try:
            await channel.send(text, allowed_mentions=allowed_mentions)
        except discord.HTTPException:
            log.warning("Could not post reminder for meeting %s", meeting_id)

        await database.mark_reminded(meeting_id)
