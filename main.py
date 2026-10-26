import logging
import os

import discord

from euler import config
from euler.bot_instance import client, tree
from euler.db import database
from euler.features import contests, diagnostics, meetings, reminders, self_roles  # noqa: F401

if config.DEV_MODE:
    from euler.features import dev  # noqa: F401


async def setup_hook():
    """Runs once, before the bot connects (unlike on_ready, which can fire repeatedly)."""
    if config.DEV_MODE and os.path.abspath(config.DB_PROD) == os.path.abspath(
        config.DEFAULT_DB_PROD
    ):
        raise RuntimeError(
            "DEV_MODE requires EULER_DB_PATH to point at a separate database "
            "(for example db/dev.sql)."
        )

    await database.init_db()

    guild = discord.Object(id=config.GUILD_ID)
    tree.copy_global_to(guild=guild)
    await tree.sync(guild=guild)

    reminders.reminder_loop.start()


client.setup_hook = setup_hook


@tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    logging.getLogger("euler").exception("command error", exc_info=error)
    msg = "Something went wrong. Tell an officer."
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


if __name__ == "__main__":
    if not config.TOKEN:
        raise SystemExit(
            "DISCORD_TOKEN is not set. Create .env from .env.example, or set "
            "EULER_ENV_FILE to the correct env file."
        )
    client.run(config.TOKEN)
