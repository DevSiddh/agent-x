# Template source: Cog-Creators/Red-DiscordBot | Difficulty: hard | Niche: bots
import os
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "{{DISCORD_TOKEN}}")
PREFIX = "{{PREFIX}}"  # e.g. !
OWNER_IDS = [{{OWNER_ID}}]
DB_URL = "sqlite:///bot.db"
LLM_API_KEY = os.environ.get("LLM_API_KEY", "{{LLM_API_KEY}}")
MUSIC_ENABLED = {{MUSIC_ENABLED}}  # True/False
MOD_LOG_CHANNEL = "{{MOD_LOG_CHANNEL}}"
