import discord
from discord import app_commands

from euler.bot_instance import tree


@tree.command(name="about", description="About Euler and its creators")
@app_commands.guild_only()
async def about(interaction: discord.Interaction):
    embed = discord.Embed(
        title="About Euler",
        description="Discord bot for Elkins Math and Science.",
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name="Co-creators",
        value="DeepSeek V4.1 Flash Free\nClaude Sonnet 5.5",
        inline=True,
    )
    embed.add_field(
        name="Maintained by",
        value="Elkins Math and Science officers",
        inline=True,
    )
    embed.add_field(
        name="Built with",
        value="Python · discord.py · SQLite",
        inline=False,
    )
    embed.add_field(
        name="Source",
        value="https://github.com/getriscvyy/euler-bot",
        inline=False,
    )
    embed.set_footer(text="Use /man for command help.")
    await interaction.response.send_message(embed=embed)
