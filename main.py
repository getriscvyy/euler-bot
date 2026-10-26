import logging

import discord

from euler import config
from euler.bot_instance import client, tree
from euler.db import database
from euler.features import contests, meetings, reminders, self_roles  # noqa: F401 (register commands)


async def setup_hook():
    """Runs once, before the bot connects (unlike on_ready, which can fire repeatedly)."""
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
    client.run(config.TOKEN)
