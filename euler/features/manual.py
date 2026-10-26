import discord
from discord import app_commands

from euler.auth import is_officer
from euler.bot_instance import tree

MEMBER_MANUAL = """**Euler — member manual**

**Signing up for contests**
Officers post contests and their IDs. Sign up with:
`/contest signup contest_id:<id> number_sense:True general_mathematics:True`

- Set a category to `True` to join it.
- Set it to `False` to leave it.
- Omit categories you don't want to change.
- You can update several categories in one command.

Example:
`/contest signup contest_id:3 number_sense:True general_mathematics:True`

Signups close at the posted deadline. After that, ask an officer to make a change.

**Roles and reminders**
React to the `/roles` panel in the announcements channel to receive a category role. Meeting and contest reminders ping only the relevant category roles. Remove your reaction to stop getting them.

**Times**
All times are America/Chicago (Central).

Use `/man` anytime for this guide. Ask an officer if you need a contest ID or other help."""

ADMIN_MANUAL = """**Euler — officer manual**

**Meetings**
`/meeting add <category> <YYYY-MM-DD HH:MM> <location>` — schedule
`/meeting list` — show IDs
`/meeting move <meeting_id> <new time>` — reschedule; re-arms reminder
`/meeting remove <meeting_id>` — delete the meeting

**Contests**
`/contest create <name> <YYYY-MM-DD HH:MM> <location> [signup_deadline]` — create
`/contest list` — IDs, deadlines, closed status, counts
`/contest deadline <contest_id> <time|clear>` — set/change/clear deadline
`/contest remove <contest_id>` — delete contest and all signups
`/contest roster <contest_id> [category]` — see signups
`/contest withdraw <contest_id> <member> [category]` — remove a signup
`/contest signup ...` — member self-service; officers can use it too

**Roles, reminders, diagnostics**
`/roles` — post/refresh the reaction-role panel
`/clock` — check the host clock against Discord (under 2s is normal)
Reminders post 60 minutes before a meeting/contest. Contest reminders ping only category roles with signups.

**Dev/testing**
With `DEV_MODE=true` and a separate `EULER_DB_PATH`: `/dev status`, `/dev dm`, `/dev contest`, `/dev meeting`, `/dev reminders`.

**Members**
Non-officers use `/contest signup` and `/man`. They can set category fields to `True`/`False` to join/leave. Signups close at the deadline.

All times are America/Chicago (Central)."""


@tree.command(name="man", description="Show the Euler manual for your permission level")
@app_commands.guild_only()
async def man(interaction: discord.Interaction):
    if not is_officer(interaction):
        await interaction.response.send_message(MEMBER_MANUAL, ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    try:
        await interaction.user.send(ADMIN_MANUAL)
    except discord.Forbidden:
        await interaction.followup.send(
            "I couldn't DM you. Here is the officer manual:", ephemeral=True
        )
        await interaction.followup.send(ADMIN_MANUAL, ephemeral=True)
        return
    except discord.HTTPException:
        await interaction.followup.send(
            "Discord rejected the DM. Here is the officer manual:", ephemeral=True
        )
        await interaction.followup.send(ADMIN_MANUAL, ephemeral=True)
        return

    await interaction.followup.send(
        "I sent the officer manual to your DMs.", ephemeral=True
    )
