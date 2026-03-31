# Template source: Cog-Creators/Red-DiscordBot | Difficulty: hard | Niche: bots
import discord
from discord.ext import commands
import openai
from config import LLM_API_KEY

client = openai.AsyncOpenAI(api_key=LLM_API_KEY)

class AIChat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.history = {}

    @commands.command(name="ask")
    async def ask(self, ctx, *, prompt: str):
        uid = ctx.author.id
        if uid not in self.history:
            self.history[uid] = []
        self.history[uid].append({"role": "user", "content": prompt})
        async with ctx.typing():
            resp = await client.chat.completions.create(
                model="{{LLM_MODEL}}",
                messages=self.history[uid][-20:]
            )
            answer = resp.choices[0].message.content
        self.history[uid].append({"role": "assistant", "content": answer})
        await ctx.reply(answer[:2000])  # Discord 2000 char limit

    @commands.command(name="reset")
    async def reset(self, ctx):
        self.history.pop(ctx.author.id, None)
        await ctx.send("Memory cleared.")

async def setup(bot):
    await bot.add_cog(AIChat(bot))
