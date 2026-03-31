# Template source: python-telegram-bot + openai | Difficulty: medium | Niche: bots
import os
BOT_TOKEN = os.environ.get("BOT_TOKEN", "{{BOT_TOKEN}}")
LLM_PROVIDER = "{{LLM_PROVIDER}}"  # openai or deepseek
LLM_API_KEY = os.environ.get("LLM_API_KEY", "{{LLM_API_KEY}}")
LLM_MODEL = "{{LLM_MODEL}}"  # gpt-4o or deepseek-chat
MAX_HISTORY = 20
MEMORY_PATH = "memory/{{USER_ID}}.jsonl"
