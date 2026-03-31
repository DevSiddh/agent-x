# Template source: python-telegram-bot + openai | Difficulty: medium | Niche: bots
from telegram import Update
from telegram.ext import ContextTypes
from services.llm import chat
from services.memory import load_history, save_message

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    save_message(user_id, "user", text)
    history = load_history(user_id)
    response = ""
    msg = await update.message.reply_text("...")
    async for chunk in chat(history):
        response += chunk
        await msg.edit_text(response)
    save_message(user_id, "assistant", response)
