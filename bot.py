import os

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

from game.database import init_db

load_dotenv()

COGS = ["cogs.game", "cogs.exploration"]


class PokemonBot(commands.Bot):
    session: aiohttp.ClientSession

    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        self.session = aiohttp.ClientSession()
        await init_db()
        for cog in COGS:
            await self.load_extension(cog)
        await self.tree.sync()
        print(f"Synced {len(self.tree.get_commands())} slash commands.")

    async def close(self) -> None:
        await self.session.close()
        await super().close()

    async def on_ready(self) -> None:
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Game(name="Pokémon  |  /start to play!")
        )


bot = PokemonBot()
bot.run(os.getenv("DISCORD_TOKEN"))
