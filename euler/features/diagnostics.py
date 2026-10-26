from datetime import datetime, timezone

import discord
from discord import app_commands

from euler import config
from euler.auth import require_officer
from euler.bot_instance import tree
from euler.utils import local_now


@tree.command(
    name="clock",
    description="Check the bot host clock against Discord's timestamp",
)
@app_commands.guild_only()
async def clock(interaction: discord.Interaction):
    if not await require_officer(interaction):
        return

    local = local_now()
    utc = datetime.now(timezone.utc)
    server = datetime.now().astimezone()

    discord_time = interaction.created_at
    if discord_time.tzinfo is None:
        discord_time = discord_time.replace(tzinfo=timezone.utc)
    drift = (utc - discord_time).total_seconds()

    if abs(drift) <= 2:
        status = "✅ Within 2 seconds of Discord."
        color = discord.Color.green()
    elif abs(drift) <= 10:
        status = (
            "⚠️ Small difference. Positive values include network latency; "
            "run the command again if it looks unusual."
        )
        color = discord.Color.yellow()
    else:
        status = "❌ Clock is more than 10 seconds off. Fix the host clock/NTP."
        color = discord.Color.red()

    embed = discord.Embed(title="Bot host clock", color=color)
    embed.add_field(
        name=f"{config.TIMEZONE_NAME} (club time)",
        value=local.strftime("%Y-%m-%d %H:%M:%S %Z (UTC%z)"),
        inline=False,
    )
    embed.add_field(
        name="UTC",
        value=utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
        inline=False,
    )
    embed.add_field(
        name="Host system timezone",
        value=server.strftime("%Y-%m-%d %H:%M:%S %Z (UTC%z)"),
        inline=False,
    )
    embed.add_field(
        name="Discord interaction time",
        value=(
            f"<t:{int(discord_time.timestamp())}:F> "
            f"({discord_time.strftime('%Y-%m-%d %H:%M:%S UTC')})"
        ),
        inline=False,
    )
    embed.add_field(
        name="Host clock minus Discord",
        value=f"{drift:+.2f} seconds",
        inline=False,
    )
    embed.add_field(name="Status", value=status, inline=False)
    embed.set_footer(
        text="The difference includes Discord/network latency; under 2s is normal."
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)
