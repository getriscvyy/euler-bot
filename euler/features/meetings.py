import sqlite3

import discord
from discord import app_commands

from euler.auth import require_officer
from euler.bot_instance import tree
from euler.constants import Category
from euler.db import database
from euler.utils import parse_time

# One parent group: /meeting add, /meeting list, /meeting move, /meeting remove
meeting = app_commands.Group(name="meeting", description="Manage club meetings", guild_only=True)


@meeting.command(name="add", description="Schedule a meeting")
@app_commands.describe(
    category="Meeting category",
    start_time="Format: YYYY-MM-DD HH:MM (24h), e.g. 2026-09-15 15:30",
    location="Room or place",
)
async def meeting_add(
    interaction: discord.Interaction,
    category: Category,
    start_time: str,
    location: str,
):
    if not await require_officer(interaction):
        return

    iso = parse_time(start_time)
    if iso is None:
        await interaction.response.send_message(
            "Bad time format. Use `YYYY-MM-DD HH:MM`, e.g. `2026-09-15 15:30`.", ephemeral=True
        )
        return

    try:
        meeting_id = await database.add_meeting(category, iso, location)
    except sqlite3.IntegrityError:   # CHECK constraint backstop
        await interaction.response.send_message("Invalid category.", ephemeral=True)
        return

    await interaction.response.send_message(
        f"Added meeting `#{meeting_id}`: **{category}** on {start_time} at {location}."
    )


@meeting.command(name="list", description="Show scheduled meetings")
async def meeting_list(interaction: discord.Interaction):
    if not await require_officer(interaction):
        return

    rows = await database.list_meetings()
    if not rows:
        await interaction.response.send_message("No meetings scheduled.")
        return

    # row = (id, category, start_time, location, reminded)
    rows.sort(key=lambda r: r[2])   # ISO strings sort chronologically
    lines = [f"`#{r[0]}` **{r[1]}** | {r[2].replace('T', ' ')} | {r[3]}" for r in rows]
    await interaction.response.send_message("\n".join(lines)[:2000])   # Discord's message cap


@meeting.command(name="move", description="Reschedule a meeting")
@app_commands.describe(
    meeting_id="The # shown in /meeting list",
    new_start_time="Format: YYYY-MM-DD HH:MM (24h)",
)
async def meeting_move(interaction: discord.Interaction, meeting_id: int, new_start_time: str):
    if not await require_officer(interaction):
        return

    iso = parse_time(new_start_time)
    if iso is None:
        await interaction.response.send_message("Bad time format. Use `YYYY-MM-DD HH:MM`.", ephemeral=True)
        return

    changed = await database.reschedule_meeting(meeting_id, iso)
    if changed == 0:
        await interaction.response.send_message(f"No meeting with id {meeting_id}.", ephemeral=True)
        return

    await interaction.response.send_message(f"Meeting `#{meeting_id}` moved to {new_start_time}.")


@meeting.command(name="remove", description="Delete a meeting")
@app_commands.describe(meeting_id="The # shown in /meeting list")
async def meeting_remove(interaction: discord.Interaction, meeting_id: int):
    if not await require_officer(interaction):
        return

    deleted = await database.delete_meeting(meeting_id)
    if deleted == 0:
        await interaction.response.send_message(f"No meeting with id {meeting_id}.", ephemeral=True)
        return

    await interaction.response.send_message(f"Meeting `#{meeting_id}` removed.")


tree.add_command(meeting)   # importing this file in main.py triggers this
