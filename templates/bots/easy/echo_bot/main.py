# Template source: python-telegram-bot | Difficulty: easy | Niche: bots
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import BOT_TOKEN, LOG_LEVEL

logging.basicConfig(level=getattr(logging, LOG_LEVEL))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! I am {{BOT_NAME}}. {{BOT_DESCRIPTION}}")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    # {{ADD_PROCESSING_LOGIC}}
    await update.message.reply_text(text)

async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"Update {update} caused error {context.error}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    app.add_error_handler(error_handler)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
