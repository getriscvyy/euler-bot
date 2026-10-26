from typing import Optional

import discord
from discord import app_commands

from euler import permissions
from euler.auth import is_officer
from euler.bot_instance import tree

ACCESS_CHOICES = [
    app_commands.Choice(name="Members", value="member"),
    app_commands.Choice(name="Officers", value="officer"),
]

perms = app_commands.Group(
    name="perms",
    description="View or change which commands members can use",
    guild_only=True,
)


async def _command_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    current = permissions.normalize_command(current)
    return [
        app_commands.Choice(name=command, value=command)
        for command in permissions.CONFIGURABLE_COMMANDS
        if current in command
    ][:25]


async def _require_staff(interaction: discord.Interaction) -> bool:
    """Permission management itself is always officer-only."""
    if is_officer(interaction):
        return True
    await interaction.response.send_message("Officers only.", ephemeral=True)
    return False


@perms.command(name="list", description="Show which commands members can use")
async def perms_list(interaction: discord.Interaction):
    if not await _require_staff(interaction):
        return

    member_commands = permissions.load_member_commands()
    member = [
        command
        for command in permissions.CONFIGURABLE_COMMANDS
        if command in member_commands
    ]
    officer = [
        command
        for command in permissions.CONFIGURABLE_COMMANDS
        if command not in member_commands
    ]

    lines = ["**Command permissions**", "", "**Members can use:**"]
    lines.extend(f"- `/{command}`" for command in member)
    if not member:
        lines.append("- None")
    lines.extend(["", "**Officers only:**"])
    lines.extend(f"- `/{command}`" for command in officer)
    if not officer:
        lines.append("- None")

    lines.extend(
        [
            "",
            "Always available: `/contest signup`, `/man`, `/about`.",
            "`/perms` itself is always officer-only.",
            "Default member access: `/contest list`.",
            "Change with `/perms set`; restore defaults with `/perms reset`.",
            "Bulk changes: edit `permissions.json` (applies immediately).",
        ]
    )
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


@perms.command(
    name="set", description="Allow members to use a command or restrict it"
)
@app_commands.describe(
    command="Command path, for example: contest list",
    access="Who can use the command",
)
@app_commands.choices(access=ACCESS_CHOICES)
@app_commands.autocomplete(command=_command_autocomplete)
async def perms_set(interaction: discord.Interaction, command: str, access: str):
    if not await _require_staff(interaction):
        return

    try:
        normalized = permissions.set_member_allowed(
            command, access == "member"
        )
    except ValueError:
        await interaction.response.send_message(
            f"`{command}` is not configurable. Use `/perms list` to see the "
            "available commands.",
            ephemeral=True,
        )
        return
    except OSError:
        await interaction.response.send_message(
            "Could not save `permissions.json`. Check the bot's file "
            "permissions.",
            ephemeral=True,
        )
        return

    target = "members" if access == "member" else "officers only"
    await interaction.response.send_message(
        f"`/{normalized}` is now available to {target}.", ephemeral=True
    )


@perms.command(
    name="reset", description="Restore default command permissions"
)
@app_commands.describe(command="Command to reset (omit to reset every command)")
@app_commands.autocomplete(command=_command_autocomplete)
async def perms_reset(
    interaction: discord.Interaction, command: Optional[str] = None
):
    if not await _require_staff(interaction):
        return

    try:
        normalized = permissions.reset_member_commands(command or None)
    except ValueError:
        await interaction.response.send_message(
            f"`{command}` is not configurable. Use `/perms list` to see the "
            "available commands.",
            ephemeral=True,
        )
        return
    except OSError:
        await interaction.response.send_message(
            "Could not save `permissions.json`. Check the bot's file "
            "permissions.",
            ephemeral=True,
        )
        return

    if normalized is None:
        await interaction.response.send_message(
            "All command permissions reset to their defaults.", ephemeral=True
        )
        return

    allowed = permissions.is_member_allowed(normalized)
    target = "members" if allowed else "officers only"
    await interaction.response.send_message(
        f"`/{normalized}` reset to its default: {target}.", ephemeral=True
    )


tree.add_command(perms)
