"""Обработчик текстовых сообщений.

Ключевой принцип: сохраняем КАЖДОЕ сообщение (даже не адресованное Мие),
а отвечаем только когда к Мие обратились:
  - в личке — всегда;
  - в группе — по @упоминанию или reply на сообщение Мии.
"""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from config import settings

logger = logging.getLogger(__name__)


def _should_respond(update: Update) -> bool:
    message = update.message
    if not message or not message.text:
        return False

    chat = message.chat
    if chat.type == "private":
        return True

    text = message.text or ""
    username = settings.BOT_USERNAME
    if username and username.lower() in text.lower():
        return True

    reply = message.reply_to_message
    if reply and reply.from_user and reply.from_user.username:
        if reply.from_user.username.lower() == username.lstrip("@").lower():
            return True

    return False


def _display_name(update: Update) -> str:
    user = update.effective_user
    if not user:
        return "аноним"
    return user.full_name or user.username or str(user.id)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.text:
        return

    chat = message.chat
    user = message.from_user
    chat_title = chat.title or (user.full_name if user else "Личный чат")
    user_id = user.id if user else None
    user_name = _display_name(update)
    text = message.text

    memory = context.application.bot_data["memory"]
    assistant = context.application.bot_data["assistant"]

    # 1. Сохраняем ВСЕ сообщения (тихо).
    await asyncio.to_thread(
        memory.remember_message,
        chat_id=chat.id,
        text=text,
        chat_title=chat_title,
        user_id=user_id,
        user_name=user_name,
        msg_type="text",
        telegram_message_id=message.message_id,
    )

    # 2. Отвечаем только если обратились к Мие.
    if not _should_respond(update):
        return

    await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.TYPING)
    try:
        response = await asyncio.to_thread(
            assistant.answer,
            text=text,
            chat_id=chat.id,
            chat_title=chat_title,
            user_id=user_id,
        )
        await message.reply_text(response)
    except Exception as e:
        logger.exception("Ошибка при ответе на сообщение: %s", e)
        await message.reply_text("Что-то пошло не так. Попробуй, пожалуйста, чуть позже.")
