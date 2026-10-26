import logging

import discord

from euler import config
from euler.bot_instance import client
from euler.constants import CATEGORIES, CATEGORY_EMOJIS

log = logging.getLogger(__name__)


def _announcement_channel():
    guild = client.get_guild(config.GUILD_ID)
    if guild is None:
        log.warning("Guild %s not found; skipping announcement", config.GUILD_ID)
        return None, None

    channel = guild.get_channel(config.ANNOUNCEMENTS_CHANNEL_ID)
    if channel is None or not hasattr(channel, "send"):
        log.warning(
            "Announcements channel %s not found; skipping announcement",
            config.ANNOUNCEMENTS_CHANNEL_ID,
        )
        return guild, None
    return guild, channel


def _role_pings(guild, categories):
    roles = []
    seen_role_ids = set()
    for category in categories:
        role_id = config.CATEGORY_ROLE_IDS.get(category, 0)
        role = guild.get_role(role_id) if role_id else None
        if role is not None and role.id not in seen_role_ids:
            roles.append(role)
            seen_role_ids.add(role.id)

    if not roles:
        return "", discord.AllowedMentions.none()
    ping = " ".join(role.mention for role in roles) + " "
    return ping, discord.AllowedMentions(roles=roles)


async def send_meeting_announcement(category, start_time, location):
    """Announce a newly created meeting. Returns True when it was posted."""
    guild, channel = _announcement_channel()
    if channel is None:
        return False

    ping, allowed_mentions = _role_pings(guild, [category])
    when = start_time.replace("T", " ")
    emoji = CATEGORY_EMOJIS.get(category, "📅")
    text = (
        f"{ping}{emoji} **New meeting:** **{category}** on {when} at "
        f"{location}."
    )
    try:
        await channel.send(text, allowed_mentions=allowed_mentions)
    except discord.HTTPException:
        log.warning("Could not post announcement for meeting in %s", location)
        return False
    return True


async def send_contest_announcement(
    contest_id, name, contest_date, location, signup_deadline=None
):
    """Announce a newly created contest and its open signups."""
    guild, channel = _announcement_channel()
    if channel is None:
        return False

    ping, allowed_mentions = _role_pings(guild, CATEGORIES)
    when = contest_date.replace("T", " ")
    deadline_text = (
        f" Signups close {signup_deadline.replace('T', ' ')}."
        if signup_deadline
        else ""
    )
    text = (
        f"{ping}📝 **New contest:** **{name}** on {when} at {location}. "
        f"Signups are open — use `/contest signup contest_id:{contest_id}`."
        f"{deadline_text}"
    )
    try:
        await channel.send(text, allowed_mentions=allowed_mentions)
    except discord.HTTPException:
        log.warning("Could not post announcement for contest %s", contest_id)
        return False
    return True
