from euler import config, permissions


def is_officer(interaction) -> bool:
    """True if the user who ran the command has the officer role."""
    roles = getattr(interaction.user, "roles", [])
    return any(role.id == config.OFFICER_ROLE_ID for role in roles)


async def require_officer(interaction) -> bool:
    """Allow officers, or members when /perms grants that command access."""
    if is_officer(interaction):
        return True

    command = getattr(interaction, "command", None)
    command_name = getattr(command, "qualified_name", None)
    if command_name and permissions.is_member_allowed(command_name):
        return True

    await interaction.response.send_message("Officers only.", ephemeral=True)
    return False
