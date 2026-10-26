from datetime import timedelta
from typing import Optional

import discord
from discord import app_commands

from euler import config
from euler.auth import require_officer
from euler.bot_instance import tree
from euler.constants import Category
from euler.db import database
from euler.features import reminders
from euler.utils import local_now

dev = app_commands.Group(
    name="dev",
    description="Development/test helpers (dev mode only)",
    guild_only=True,
)


def _db_time(value):
    return value.replace(tzinfo=None).isoformat(timespec="seconds")


@dev.command(name="dm", description="Send yourself a test DM")
async def dev_dm(interaction: discord.Interaction):
    if not await require_officer(interaction):
        return

    now = local_now()
    try:
        await interaction.user.send(
            "✅ Euler test DM\n"
            f"Sent at {now.strftime('%Y-%m-%d %H:%M:%S %Z')}.\n"
            "If you received this, DMs from the bot are working."
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "I couldn't DM you. Check your privacy settings or allow DMs from "
            "this server's members.",
            ephemeral=True,
        )
        return
    except discord.HTTPException:
        await interaction.response.send_message(
            "Discord rejected the DM. Check the logs.", ephemeral=True
        )
        return

    await interaction.response.send_message("Test DM sent.", ephemeral=True)


@dev.command(name="contest", description="Create a disposable contest in the dev DB")
async def dev_contest(interaction: discord.Interaction):
    if not await require_officer(interaction):
        return

    now = local_now().replace(second=0, microsecond=0)
    start = now + timedelta(minutes=30)
    deadline = now + timedelta(minutes=20)
    name = f"Dev Contest {now.strftime('%H:%M:%S')}"
    contest_id = await database.create_contest(
        name,
        _db_time(start),
        "Dev Room",
        signup_deadline=_db_time(deadline),
    )
    await interaction.response.send_message(
        f"Created dev contest `#{contest_id}`: **{name}** at "
        f"{start.strftime('%Y-%m-%d %H:%M')} (Chicago). "
        f"Signups close {deadline.strftime('%H:%M')}. "
        "It will be included in the next reminder check.",
        ephemeral=True,
    )


@dev.command(name="meeting", description="Create a disposable meeting in the dev DB")
@app_commands.describe(category="Meeting category (defaults to General Mathematics)")
async def dev_meeting(
    interaction: discord.Interaction,
    category: Optional[Category] = None,
):
    if not await require_officer(interaction):
        return

    category = category or "General Mathematics"
    now = local_now().replace(second=0, microsecond=0)
    start = now + timedelta(minutes=30)
    meeting_id = await database.add_meeting(
        category, _db_time(start), "Dev Room"
    )
    await interaction.response.send_message(
        f"Created dev meeting `#{meeting_id}`: **{category}** at "
        f"{start.strftime('%Y-%m-%d %H:%M')} (Chicago). "
        "It will be included in the next reminder check.",
        ephemeral=True,
    )


@dev.command(name="reminders", description="Run the reminder checks immediately")
async def dev_reminders(interaction: discord.Interaction):
    if not await require_officer(interaction):
        return

    await interaction.response.defer(ephemeral=True)
    meetings_sent, contests_sent = await reminders.send_due_reminders()
    await interaction.followup.send(
        f"Reminder check complete: {meetings_sent} meeting(s), "
        f"{contests_sent} contest(s) sent.",
        ephemeral=True,
    )


@dev.command(name="status", description="Show the running dev configuration")
async def dev_status(interaction: discord.Interaction):
    if not await require_officer(interaction):
        return

    production_db = config.DB_PROD == config.DEFAULT_DB_PROD
    await interaction.response.send_message(
        "\n".join(
            [
                "**Dev status**",
                f"DEV_MODE: `{config.DEV_MODE}`",
                f"DB: `{config.DB_PROD}`",
                f"Production DB: `{production_db}`",
                f"Timezone: `{config.TIMEZONE_NAME}`",
            ]
        ),
        ephemeral=True,
    )


if config.DEV_MODE:
    tree.add_command(dev)
