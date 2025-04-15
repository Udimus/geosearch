#!/usr/bin/env python3

import logging
import os
from typing import List, Tuple, Any, Optional

from telegram import ForceReply, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from search_engine import HouseSearcher, hash_tags


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

searchers = {}
user_states = {}

NO_TAGS_MESSAGE = (
   "Не заданы тэги для области поиска.\n"
    + "/state -- посмотреть настройки текущей сессии.\n"
    + "/tags -- ввести через пробел тэг/тэги для определения области поиска."
)

def clean_user_state(user_id: int) -> None:
    if user_id in user_states:
        del user_states[user_id]

def get_user_state(user_id: int) -> None:
    return user_states.get(user_id, {})

def update_user_state(user_id: int, key: str, value: Any) -> None:
    state = get_user_state(user_id)
    state[key] = value
    user_states[user_id] = state

def check_searcher(user_id: int) -> Optional[int]:
    state = get_user_state(user_id)
    if "searcher" in state and state["searcher"] in searchers:
        return state["searcher"]

def log_user_action(update: Update, action: str) -> None:
    logger.info(f"user_id: {update.message.from_user.id}, action: {action}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_user_action(update, "start")
    await update.message.reply_text(
            "Привет! Этот бот может искать адреса по формулам."
        )
    text = "С помощью /tags введите тэг/тэги, по которым будет осуществляться поиск.\n/help выведет список всех команд."
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_user_action(update, "stop")
    clean_user_state(update.message.from_user.id)
    await update.message.reply_text("Сессия завершена.")

async def tags(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_user_action(update, "tags")
    tags = context.args
    input_tags_hash = hash_tags(tags)
    user_id = update.message.from_user.id
    if input_tags_hash not in searchers:
        s = HouseSearcher(tags)
        searchers[hash(s)] = s
        update_user_state(user_id, "searcher", hash(s))
    else:
        update_user_state(user_id, "searcher", input_tags_hash)
    state = get_user_state(user_id)
    tags_string = ", ".join(searchers[state["searcher"]].found_tags)
    text = f"Текущий поиск по тэгам: {tags_string}"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

async def subnumbers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_user_action(update, "subnumbers")
    flag = context.args[0]
    if flag == "1":
        update_user_state(update.message.from_user.id, "subnumbers", True)

def _search(update: Update) -> str:
    searcher_hash = check_searcher(update.message.from_user.id)
    if searcher_hash is None:
        return NO_TAGS_MESSAGE
    s = searchers[searcher_hash]
    try:
        subnumbers = get_user_state(update.message.from_user.id).get("subnumbers", False)
        return "\n".join(s.search(update.message.text, subnumbers))
    except:
        return "Что-то пошло не так. Проверьте корректность формулы."
    
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_user_action(update, "search")
    await update.message.reply_text(_search(update))

def _streets(update: Update) -> str:
    searcher_hash = check_searcher(update.message.from_user.id)
    if searcher_hash is None:
        return NO_TAGS_MESSAGE
    return "\n".join(searchers[searcher_hash].get_all_streets())

async def streets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_user_action(update, "streets")
    await update.message.reply_text(_streets(update))

# async def location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     message = update.message
#     user_location_lonlat = (update.message.location.longitude, update.message.location.latitude)
#     text = f"Долгота: {user_location_lonlat[0]}, Широта: {user_location_lonlat[1]}"
#     await update.message.reply_text(text)

async def get_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_user_action(update, "get_state")
    user_id = update.message.from_user.id
    state = get_user_state(user_id)
    text = ""
    if check_searcher(user_id) is None:
        text += f"Сейчас тэги не заданы;\n"
    else:
        tags_string = ", ".join(searchers[state["searcher"]].found_tags)
        text += f"Сейчас поиск осуществляется по тэгам: [{tags_string}];\n"
    if state.get("subnumbers", False):
        text += f"Сейчас ищутся дома c корпусами или литерами;\n"
    else:
        text += f"Сейчас ищутся дома без корпусов или литер;\n"
    await update.message.reply_text(text)

async def get_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_user_action(update, "get_help")
    text = (
        "/start -- начать новую сессию.\n"
        + "/stop -- закончить сессию.\n"
        + "/state -- посмотреть настройки текущей сессии.\n"
        + "/tags -- ввести через пробел тэг/тэги для определения области поиска.\n"
        + "/streets -- список улиц в заданной области поиска.\n"
        + "/subnumbers -- 1, чтобы искать только по домам с корпусами, 0 -- только по домам без корпусов.\n"
        + "Для поиска по формуле просто введите её без дополнительных команд."
    )
    await update.message.reply_text(text)

def main() -> None:
    application = Application.builder().token(os.environ["TELEGRAM_GEOBOT_TOKEN"]).build()

    application.add_handler(CommandHandler("start", start, has_args=False))
    application.add_handler(CommandHandler("stop", stop, has_args=False))
    application.add_handler(CommandHandler("help", get_help, has_args=False))
    application.add_handler(CommandHandler("state", get_state, has_args=False))
    application.add_handler(CommandHandler("streets", streets, has_args=False))
    application.add_handler(CommandHandler("tags", tags, has_args=True))
    application.add_handler(CommandHandler("subnumbers", subnumbers, has_args=1))
    
    # application.add_handler(MessageHandler(filters.LOCATION & ~filters.COMMAND, location))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
