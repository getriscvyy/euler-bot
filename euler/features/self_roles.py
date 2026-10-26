import logging

import discord
from discord import app_commands

from euler import config
from euler.auth import require_officer
from euler.bot_instance import client, tree
from euler.constants import CATEGORIES, CATEGORY_EMOJIS
from euler.db import database

log = logging.getLogger(__name__)


def _configured_roles(guild):
    """(category, emoji, role) for each category whose role ID is configured."""
    entries = []
    for category in CATEGORIES:
        role_id = config.CATEGORY_ROLE_IDS.get(category, 0)
        role = guild.get_role(role_id) if role_id else None
        if role is None:
            continue
        entries.append((category, CATEGORY_EMOJIS[category], role))
    return entries


def _panel_embed(entries):
    embed = discord.Embed(
        title="Event Notifications",
        description=(
            "React with the emoji for each event you want reminders for.\n"
            "Remove your reaction at any time to stop those notifications."
        ),
    )
    for category, emoji, role in entries:
        embed.add_field(
            name=f"{emoji} {category}",
            value=f"React for {role.mention}",
            inline=False,
        )
    embed.set_footer(text="You can choose more than one event.")
    return embed


@tree.command(
    name="roles",
    description="Post or refresh the event notification reaction-role panel",
)
@app_commands.guild_only()
async def roles_panel(interaction: discord.Interaction):
    if not await require_officer(interaction):
        return

    guild = interaction.guild
    channel = guild.get_channel(config.ANNOUNCEMENTS_CHANNEL_ID)
    if channel is None or not hasattr(channel, "send"):
        await interaction.response.send_message(
            "Announcements channel not found. Check ANNOUNCEMENTS_CHANNEL_ID.",
            ephemeral=True,
        )
        return

    entries = _configured_roles(guild)
    if not entries:
        await interaction.response.send_message(
            "No category role IDs are configured. Set the four *_ROLE_ID variables.",
            ephemeral=True,
        )
        return
    configured = {entry[0] for entry in entries}
    missing = [category for category in CATEGORIES if category not in configured]

    # Replace the old panel so repeated runs don't leave stale messages behind.
    old_panel = await database.get_role_panel(guild.id)
    if old_panel is not None:
        old_channel_id, old_message_id = old_panel
        old_channel = guild.get_channel(old_channel_id)
        if old_channel is not None and hasattr(old_channel, "fetch_message"):
            try:
                old_message = await old_channel.fetch_message(old_message_id)
                await old_message.delete()
            except discord.HTTPException:
                log.warning("Could not delete old role panel %s", old_message_id)

    panel_message = await channel.send(
        embed=_panel_embed(entries),
        allowed_mentions=discord.AllowedMentions.none(),
    )

    mappings = []
    for category, emoji, role in entries:
        try:
            await panel_message.add_reaction(emoji)
        except discord.HTTPException:
            log.warning("Could not add %s reaction for %s", emoji, category)
            continue
        mappings.append((emoji, role.id))

    if not mappings:
        try:
            await panel_message.delete()
        except discord.HTTPException:
            pass
        await interaction.response.send_message(
            "Could not add any reactions to the role panel.", ephemeral=True
        )
        return

    await database.replace_role_panel(
        guild.id, channel.id, panel_message.id, mappings
    )
    message = f"Event notification role panel posted in {channel.mention}."
    if missing:
        message += f" Missing role IDs: {', '.join(missing)}."
    await interaction.response.send_message(message, ephemeral=True)


async def _apply_reaction_role(payload, *, add):
    if payload.guild_id is None:
        return
    if client.user is not None and payload.user_id == client.user.id:
        return

    role_id = await database.get_reaction_role(payload.message_id, str(payload.emoji))
    if role_id is None:
        return

    guild = client.get_guild(payload.guild_id)
    if guild is None:
        return

    role = guild.get_role(role_id)
    if role is None:
        log.warning("Reaction role %s no longer exists", role_id)
        return

    member = guild.get_member(payload.user_id)
    if member is None:
        try:
            member = await guild.fetch_member(payload.user_id)
        except discord.HTTPException:
            return
    if member.bot:
        return

    if guild.me is not None and role >= guild.me.top_role:
        log.warning("Cannot manage role %s: it is above the bot's top role", role_id)
        return

    try:
        if add:
            await member.add_roles(role, reason="Event notification reaction role")
        else:
            await member.remove_roles(role, reason="Event notification reaction role")
    except discord.HTTPException:
        log.warning("Could not update reaction role %s for %s", role_id, member.id)


@client.event
async def on_raw_reaction_add(payload):
    await _apply_reaction_role(payload, add=True)


@client.event
async def on_raw_reaction_remove(payload):
    await _apply_reaction_role(payload, add=False)
