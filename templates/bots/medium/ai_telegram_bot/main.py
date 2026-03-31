# Template source: python-telegram-bot + openai | Difficulty: medium | Niche: bots
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from handlers.commands import start, reset, help_cmd
from handlers.messages import handle_message
from config import BOT_TOKEN

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
