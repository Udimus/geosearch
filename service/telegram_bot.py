#!/usr/bin/env python3

import logging
import os

from telegram import ForceReply, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

CONVERSATIONS = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    await update.message.reply_text(
            "Привет! Этот бот может искать адреса по формулам."
        )
    text = "Введите тэг/тэги, по которым будет осуществляться поиск."
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """End Conversation by command."""
    await update.message.reply_text("Сессия завершена.")
    if update.message.from_user.id in CONVERSATIONS:
        del CONVERSATIONS[update.message.from_user.id]

async def tags(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tags = context.args
    tags_string = ', '.join(tags)
    text = f"Нашёл записи по тэгам: {tags_string}"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = f"Не нашёл ничего по запросу [{update.message.text}]"
    await update.message.reply_text(text)

async def location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    user_location_lonlat = (update.message.location.longitude, update.message.location.latitude)
    text = f"Долгота: {user_location_lonlat[0]}, Широта: {user_location_lonlat[1]}"
    await update.message.reply_text(text)

def main() -> None:
    application = Application.builder().token(os.environ["TELEGRAM_GEOBOT_TOKEN"]).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("tags", tags))
    
    application.add_handler(MessageHandler(filters.LOCATION & ~filters.COMMAND, location))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
