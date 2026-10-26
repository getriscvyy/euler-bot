import discord
from discord import app_commands

intents = discord.Intents.default()
intents.members = True
intents.reactions = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
