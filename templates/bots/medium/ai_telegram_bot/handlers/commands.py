# Template source: python-telegram-bot + openai | Difficulty: medium | Niche: bots
from telegram import Update
from telegram.ext import ContextTypes
import os, glob
from config import MEMORY_PATH

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! I am {{BOT_NAME}}. Ask me anything.")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    path = MEMORY_PATH.replace("{{USER_ID}}", str(user_id))
    if os.path.exists(path):
        os.remove(path)
    await update.message.reply_text("Memory cleared.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("/start - Start\n/reset - Clear memory\n/model - Show model\n/help - Help")
