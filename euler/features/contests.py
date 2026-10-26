from typing import Optional

import discord
from discord import app_commands

from euler.auth import require_officer
from euler.bot_instance import tree
from euler.constants import CATEGORIES, Category
from euler.db import database
from euler.utils import parse_time

# /contest create (officer), /contest list (officer), /contest signup (anyone),
# /contest withdraw (officer), /contest roster (officer)
contest = app_commands.Group(name="contest", description="Contests and signups", guild_only=True)


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


@contest.command(name="list", description="Show contests and subcontest signup counts")
async def contest_list(interaction: discord.Interaction):
    if not await require_officer(interaction):
        return

    rows = await database.list_contests()
    if not rows:
        await interaction.response.send_message("No contests yet.")
        return

    counts = await database.get_contest_signup_counts()
    by_contest = {}
    for contest_id, category, count in counts:
        by_contest.setdefault(contest_id, {})[category] = count

    lines = []
    for contest_id, name, contest_date, location, signup_count in rows:
        breakdown = by_contest.get(contest_id, {})
        parts = [
            f"{category}: {breakdown[category]}"
            for category in CATEGORIES
            if breakdown.get(category)
        ]
        legacy = breakdown.get(None)
        if legacy:
            parts.append(f"Unspecified: {legacy}")
        detail = f" — {', '.join(parts)}" if parts else ""
        entry_word = "entry" if signup_count == 1 else "entries"
        lines.append(
            f"`#{contest_id}` **{name}** | {contest_date.replace('T', ' ')} | "
            f"{location} | {signup_count} {entry_word}{detail}"
        )

    await interaction.response.send_message("\n".join(lines)[:2000])


@contest.command(name="signup", description="Sign up for a contest subcontest")
@app_commands.describe(
    contest_id="The # shown in /contest list",
    category="Which subcontest to sign up for",
)
async def contest_signup(interaction: discord.Interaction, contest_id: int, category: Category):
    # No officer/admin check: every member can sign up for a subcontest.
    result = await database.signup_contest(contest_id, interaction.user.id, category)
    messages = {
        "ok": f"You're signed up for **{category}** in contest `#{contest_id}`.",
        "already": f"You're already signed up for **{category}** in contest `#{contest_id}`.",
        "no_contest": f"No contest with id {contest_id}.",
        "bad_category": "That isn't a valid subcontest.",
    }
    await interaction.response.send_message(messages[result], ephemeral=(result != "ok"))


@contest.command(name="withdraw", description="Withdraw a member from one or all contest subcontests")
@app_commands.describe(
    contest_id="The # shown in /contest list",
    user="Member to withdraw",
    category="Subcontest to withdraw from (omit to withdraw from all)",
)
async def contest_withdraw(
    interaction: discord.Interaction,
    contest_id: int,
    user: discord.Member,
    category: Optional[Category] = None,
):
    if not await require_officer(interaction):
        return

    removed = await database.withdraw_contest(
        contest_id, user.id, category=category
    )
    target = (
        f"**{category}** in contest `#{contest_id}`"
        if category is not None
        else f"contest `#{contest_id}`"
    )
    if removed == 0:
        await interaction.response.send_message(
            f"{user.mention} wasn't signed up for {target}.", ephemeral=True
        )
        return
    await interaction.response.send_message(
        f"Withdrew {user.mention} from {target}.", ephemeral=True
    )


@contest.command(name="roster", description="Who signed up, grouped by subcontest")
@app_commands.describe(
    contest_id="The # shown in /contest list",
    category="Only show one subcontest (omit for all)",
)
async def contest_roster(
    interaction: discord.Interaction,
    contest_id: int,
    category: Optional[Category] = None,
):
    if not await require_officer(interaction):
        return

    contest = await database.get_contest(contest_id)
    if contest is None:
        await interaction.response.send_message(
            f"No contest with id {contest_id}.", ephemeral=True
        )
        return
    contest_name = contest[1]

    rows = await database.get_roster(contest_id, category=category)
    if not rows:
        if category is None:
            message = f"Nobody signed up for **{contest_name}** yet."
        else:
            message = f"Nobody signed up for **{category}** in **{contest_name}** yet."
        await interaction.response.send_message(message, ephemeral=True)
        return

    if category is not None:
        title = f"Roster for **{contest_name}** (`#{contest_id}`) — **{category}**"
        text = "\n".join(f"<@{user_id}>" for user_id, _ in rows)
    else:
        grouped = {}
        for user_id, signup_category in rows:
            grouped.setdefault(signup_category, []).append(user_id)

        sections = []
        for signup_category in CATEGORIES:
            user_ids = grouped.get(signup_category, [])
            if user_ids:
                names = "\n".join(f"<@{user_id}>" for user_id in user_ids)
                sections.append(f"**{signup_category}**\n{names}")

        legacy = grouped.get(None, [])
        if legacy:
            names = "\n".join(f"<@{user_id}>" for user_id in legacy)
            sections.append(f"**Unspecified (legacy)**\n{names}")

        title = f"Roster for **{contest_name}** (`#{contest_id}`)"
        text = "\n\n".join(sections)

    # allowed_mentions=none: show names as mentions without pinging everyone
    await interaction.response.send_message(
        f"{title}:\n{text}"[:2000],
        allowed_mentions=discord.AllowedMentions.none(),
    )


tree.add_command(contest)
