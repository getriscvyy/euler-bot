from euler import config


def is_officer(interaction) -> bool:
    """True if the user who ran the command has the officer role."""
    roles = getattr(interaction.user, "roles", [])
    return any(role.id == config.OFFICER_ROLE_ID for role in roles)


async def require_officer(interaction) -> bool:
    """Sends the rejection itself; returns True if the caller may proceed."""
    if not is_officer(interaction):
        await interaction.response.send_message("Officers only.", ephemeral=True)
        return False
    return True
