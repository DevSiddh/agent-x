# Template source: Cog-Creators/Red-DiscordBot | Difficulty: hard | Niche: bots
import discord
from discord.ext import commands
from config import MOD_LOG_CHANNEL

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason="No reason"):
        await member.ban(reason=reason)
        await ctx.send(f"Banned {member.mention} | Reason: {reason}")
        await self._log(ctx.guild, f"BAN: {member} by {ctx.author} | {reason}")

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason="No reason"):
        await member.kick(reason=reason)
        await ctx.send(f"Kicked {member.mention}")
        await self._log(ctx.guild, f"KICK: {member} by {ctx.author} | {reason}")

    async def _log(self, guild, message):
        channel = discord.utils.get(guild.text_channels, name=MOD_LOG_CHANNEL)
        if channel:
            await channel.send(message)
        # {{ADD_MORE_MOD_ACTIONS}}

async def setup(bot):
    await bot.add_cog(Moderation(bot))
