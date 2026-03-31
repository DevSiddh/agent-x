# Template source: Cog-Creators/Red-DiscordBot | Difficulty: hard | Niche: bots
import discord
from discord.ext import commands
from config import DISCORD_TOKEN, PREFIX, OWNER_IDS

class {{BOT_CLASS}}(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=PREFIX, intents=intents, owner_ids=set(OWNER_IDS))

    async def setup_hook(self):
        # Core engine: load all cogs on startup
        for cog in ["cogs.moderation", "cogs.music", "cogs.ai_chat"]:
            try:
                await self.load_extension(cog)
                print(f"Loaded: {cog}")
            except Exception as e:
                print(f"Failed to load {cog}: {e}")
        await self.tree.sync()

    async def on_ready(self):
        print(f"Bot ready: {self.user} | Guilds: {len(self.guilds)}")
        await self.change_presence(activity=discord.Game(name="{{BOT_STATUS}}"))

bot = {{BOT_CLASS}}()

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
