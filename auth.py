import config


def is_officer(interaction) -> bool:
    """True if the user who ran the command has the officer role."""
    roles = getattr(interaction.user, "roles", [])
    return any(role.id == config.OFFICER_ROLE_ID for role in roles)
