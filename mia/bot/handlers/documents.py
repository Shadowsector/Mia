"""Обработка входящих документов и голосовых.

Заглушки на Этап 0. На следующих этапах здесь появятся:
  - парсинг docx/xlsx/pdf (+ OCR для сканов), затем dwg;
  - summary документов (в т.ч. табличный) и реестр «есть/нет/ждём»;
  - STT для голосовых (локальный Whisper).
Пока мы фиксируем сам факт получения файла в память.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.document:
        return

    doc = message.document
    chat = message.chat
    user = message.from_user
    chat_title = chat.title or (user.full_name if user else "Личный чат")

    memory = context.application.bot_data["memory"]
    note = f"[документ получен: {doc.file_name}, {doc.mime_type or 'тип неизвестен'}]"
    memory.remember_message(
        chat_id=chat.id,
        text=note,
        chat_title=chat_title,
        user_id=user.id if user else None,
        user_name=(user.full_name if user else ""),
        msg_type="document",
        telegram_message_id=message.message_id,
    )

    await message.reply_text(
        f"Получила файл «{doc.file_name}». Разбор документов подключим на следующем этапе — "
        "пока я запомнила, что он пришёл."
    )


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return
    await message.reply_text(
        "Голосовые я пока не расшифровываю — скоро прикрутим распознавание речи. "
        "Можешь пока написать текстом?"
    )
