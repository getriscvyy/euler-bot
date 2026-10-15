import discord
from discord import app_commands

from auth import is_officer
from bot_instance import tree
from db import database
from utils import parse_time

# /contest create (officer), /contest list, /contest signup, /contest withdraw, /contest roster (officer)
contest = app_commands.Group(name="contest", description="Contests and signups", guild_only=True)


async def require_officer(interaction: discord.Interaction):
    if not is_officer(interaction):
        await interaction.response.send_message("Officers only.", ephemeral=True)
        return False
    return True


@contest.command(name="create", description="Create a contest")
@app_commands.describe(
    name="Contest name",
    contest_date="Format: YYYY-MM-DD HH:MM (24h)",
    location="Where it takes place",
)
async def contest_create(interaction: discord.Interaction, name: str, contest_date: str, location: str):
    if not await require_officer(interaction):
        return

    iso = parse_time(contest_date)
    if iso is None:
        await interaction.response.send_message("Bad time format. Use `YYYY-MM-DD HH:MM`.", ephemeral=True)
        return

    contest_id = await database.create_contest(name, iso, location)
    await interaction.response.send_message(
        f"Created contest `#{contest_id}`: **{name}** on {contest_date} at {location}."
    )


@contest.command(name="list", description="Show contests and signup counts")
async def contest_list(interaction: discord.Interaction):
    rows = await database.list_contests()
    if not rows:
        await interaction.response.send_message("No contests yet.")
        return

    # row = (id, name, contest_date, location, signup_count)
    lines = [
        f"`#{r[0]}` **{r[1]}** | {r[2].replace('T', ' ')} | {r[3]} | {r[4]} signed up"
        for r in rows
    ]
    await interaction.response.send_message("\n".join(lines)[:2000])


@contest.command(name="signup", description="Sign yourself up for a contest")
@app_commands.describe(contest_id="The # shown in /contest list")
async def contest_signup(interaction: discord.Interaction, contest_id: int):
    result = await database.signup_contest(contest_id, interaction.user.id)
    messages = {
        "ok": f"You're signed up for contest `#{contest_id}`.",
        "already": "You're already signed up for that one.",
        "no_contest": f"No contest with id {contest_id}.",
    }
    await interaction.response.send_message(messages[result], ephemeral=(result != "ok"))


@contest.command(name="withdraw", description="Remove yourself from a contest")
@app_commands.describe(contest_id="The # shown in /contest list")
async def contest_withdraw(interaction: discord.Interaction, contest_id: int):
    removed = await database.withdraw_contest(contest_id, interaction.user.id)
    if removed == 0:
        await interaction.response.send_message("You weren't signed up for that contest.", ephemeral=True)
        return
    await interaction.response.send_message(f"You've withdrawn from contest `#{contest_id}`.", ephemeral=True)


@contest.command(name="roster", description="Who signed up for a contest")
@app_commands.describe(contest_id="The # shown in /contest list")
async def contest_roster(interaction: discord.Interaction, contest_id: int):
    if not await require_officer(interaction):
        return

    user_ids = await database.get_roster(contest_id)
    if not user_ids:
        await interaction.response.send_message("Nobody signed up yet.", ephemeral=True)
        return

    # allowed_mentions=none: show names as mentions without pinging everyone
    text = "\n".join(f"<@{uid}>" for uid in user_ids)
    await interaction.response.send_message(
        f"Roster for `#{contest_id}`:\n{text}"[:2000],
        allowed_mentions=discord.AllowedMentions.none(),
    )


tree.add_command(contest)
