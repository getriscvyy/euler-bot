from typing import Optional

import discord
from discord import app_commands

from euler import announcements
from euler.auth import require_officer
from euler.bot_instance import tree
from euler.constants import CATEGORIES, Category
from euler.db import database
from euler.utils import local_now_iso, parse_time

# /contest create/remove/deadline/withdraw/roster are officer-only by default.
# /contest list is member-accessible by default; /contest signup is always public.
contest = app_commands.Group(name="contest", description="Contests and signups", guild_only=True)


@contest.command(name="create", description="Create a contest")
@app_commands.describe(
    name="Contest name",
    contest_date="Format: YYYY-MM-DD HH:MM (24h), America/Chicago",
    location="Where it takes place",
    signup_deadline="Optional signup deadline: YYYY-MM-DD HH:MM (24h)",
)
async def contest_create(
    interaction: discord.Interaction,
    name: str,
    contest_date: str,
    location: str,
    signup_deadline: Optional[str] = None,
):
    if not await require_officer(interaction):
        return

    iso = parse_time(contest_date)
    if iso is None:
        await interaction.response.send_message(
            "Bad time format. Use `YYYY-MM-DD HH:MM`.", ephemeral=True
        )
        return

    deadline_iso = None
    if signup_deadline is not None:
        deadline_iso = parse_time(signup_deadline)
        if deadline_iso is None:
            await interaction.response.send_message(
                "Bad deadline format. Use `YYYY-MM-DD HH:MM`.", ephemeral=True
            )
            return
        if deadline_iso >= iso:
            await interaction.response.send_message(
                "The signup deadline must be before the contest date/time.",
                ephemeral=True,
            )
            return

    await interaction.response.defer()
    contest_id = await database.create_contest(
        name, iso, location, signup_deadline=deadline_iso
    )
    announced = await announcements.send_contest_announcement(
        contest_id, name, iso, location, signup_deadline=deadline_iso
    )
    deadline_note = (
        f" Signups close {signup_deadline}." if signup_deadline else ""
    )
    announcement_note = (
        ""
        if announced
        else " Could not post the announcement; check ANNOUNCEMENTS_CHANNEL_ID "
        "and permissions."
    )
    await interaction.followup.send(
        f"Created contest `#{contest_id}`: **{name}** on {contest_date} at "
        f"{location}.{deadline_note}{announcement_note}"
    )


@contest.command(name="deadline", description="Set or clear a contest signup deadline")
@app_commands.describe(
    contest_id="The # shown in /contest list",
    deadline="YYYY-MM-DD HH:MM, or 'clear' to remove the deadline",
)
async def contest_deadline(
    interaction: discord.Interaction, contest_id: int, deadline: str
):
    if not await require_officer(interaction):
        return

    contest = await database.get_contest(contest_id)
    if contest is None:
        await interaction.response.send_message(
            f"No contest with id {contest_id}.", ephemeral=True
        )
        return

    if deadline.strip().lower() in {"clear", "none", "off"}:
        await database.update_contest_deadline(contest_id, None)
        await interaction.response.send_message(
            f"Cleared the signup deadline for contest `#{contest_id}`."
        )
        return

    iso = parse_time(deadline)
    if iso is None:
        await interaction.response.send_message(
            "Bad time format. Use `YYYY-MM-DD HH:MM` or `clear`.",
            ephemeral=True,
        )
        return
    if iso >= contest[2]:
        await interaction.response.send_message(
            "The signup deadline must be before the contest date/time.",
            ephemeral=True,
        )
        return

    await database.update_contest_deadline(contest_id, iso)
    closed_note = " Signups are now closed." if local_now_iso() >= iso else ""
    await interaction.response.send_message(
        f"Signup deadline for contest `#{contest_id}` set to {deadline}."
        f"{closed_note}"
    )


@contest.command(name="remove", description="Delete a contest and all its signups")
@app_commands.describe(contest_id="The # shown in /contest list")
async def contest_remove(interaction: discord.Interaction, contest_id: int):
    if not await require_officer(interaction):
        return

    contest = await database.get_contest(contest_id)
    if contest is None:
        await interaction.response.send_message(
            f"No contest with id {contest_id}.", ephemeral=True
        )
        return

    deleted = await database.delete_contest(contest_id)
    if deleted == 0:
        await interaction.response.send_message(
            f"No contest with id {contest_id}.", ephemeral=True
        )
        return

    await interaction.response.send_message(
        f"Removed contest `#{contest_id}`: **{contest[1]}** and its signups."
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
    for contest_id, name, contest_date, location, deadline, signup_count in rows:
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
        if deadline is None:
            deadline_text = "no deadline"
        else:
            closed = local_now_iso() >= deadline
            deadline_text = f"deadline {deadline.replace('T', ' ')}"
            if closed:
                deadline_text += " (closed)"
        entry_word = "entry" if signup_count == 1 else "entries"
        lines.append(
            f"`#{contest_id}` **{name}** | {contest_date.replace('T', ' ')} | "
            f"{location} | {deadline_text} | {signup_count} {entry_word}{detail}"
        )

    await interaction.response.send_message("\n".join(lines)[:2000])


@contest.command(name="signup", description="Add or remove yourself from contest subcontests")
@app_commands.describe(
    contest_id="The # shown in /contest list",
    number_sense="True to add, False to remove, omit to leave unchanged",
    general_mathematics="True to add, False to remove, omit to leave unchanged",
    calculator_applications="True to add, False to remove, omit to leave unchanged",
    general_science="True to add, False to remove, omit to leave unchanged",
)
async def contest_signup(
    interaction: discord.Interaction,
    contest_id: int,
    number_sense: Optional[bool] = None,
    general_mathematics: Optional[bool] = None,
    calculator_applications: Optional[bool] = None,
    general_science: Optional[bool] = None,
):
    # No officer/admin check: every member manages their own signups.
    selections = {}
    for category, wanted in (
        ("Number Sense", number_sense),
        ("General Mathematics", general_mathematics),
        ("Calculator Applications", calculator_applications),
        ("General Science", general_science),
    ):
        if wanted is not None:
            selections[category] = wanted

    if not selections:
        await interaction.response.send_message(
            "Choose at least one category: True adds it, False removes it.",
            ephemeral=True,
        )
        return

    result = await database.update_contest_signups(
        contest_id, interaction.user.id, selections
    )
    if result == "no_contest":
        await interaction.response.send_message(
            f"No contest with id {contest_id}. Use `/contest list` to see the "
            "contest IDs.",
            ephemeral=True,
        )
        return
    if result == "bad_category":
        await interaction.response.send_message(
            "That isn't a valid subcontest.", ephemeral=True
        )
        return
    if result == "closed":
        await interaction.response.send_message(
            f"Signups for contest `#{contest_id}` are closed.", ephemeral=True
        )
        return
    if not result:
        await interaction.response.send_message(
            f"No changes for contest `#{contest_id}`.", ephemeral=True
        )
        return

    added = [category for action, category in result if action == "added"]
    removed = [category for action, category in result if action == "removed"]
    parts = []
    if added:
        parts.append("signed up for " + ", ".join(f"**{category}**" for category in added))
    if removed:
        parts.append("removed " + ", ".join(f"**{category}**" for category in removed))
    await interaction.response.send_message(
        f"Updated contest `#{contest_id}`: {'; '.join(parts)}."
    )


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
