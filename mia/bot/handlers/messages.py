"""Обработчик текстовых сообщений.

Ключевой принцип: сохраняем КАЖДОЕ сообщение (даже не адресованное Мие),
а отвечаем только когда к Мие обратились:
  - в личке — всегда;
  - в группе — по @упоминанию или reply на сообщение Мии.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from config import settings
from mia.documents import summarizer

logger = logging.getLogger(__name__)


def _wants_summary(text: str) -> bool:
    t = text.lower()
    return "сводк" in t or ("разбер" in t and "документ" in t)


def _wants_registry(text: str) -> bool:
    t = text.lower()
    return "реестр" in t


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

    # 2a. Запрос сводки по документу.
    if _wants_summary(text):
        await _handle_summary_request(update, context)
        return

    # 2b. Запрос общего реестра.
    if _wants_registry(text):
        await _handle_registry_request(update, context)
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


async def _handle_summary_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    chat = message.chat
    db = context.application.bot_data["db"]

    from mia.bot.handlers.documents import ingest_document

    doc = None
    reply = message.reply_to_message
    if reply:
        doc = db.get_document_by_tg_message(chat.id, reply.message_id)
        # Файл прислан раньше (напр. на старой версии) и ещё не в базе — разберём сейчас.
        if doc is None and reply.document:
            try:
                doc = await ingest_document(reply, context)
            except Exception as e:
                logger.exception("Не удалось разобрать файл из reply: %s", e)
    if doc is None:
        doc = db.latest_document(chat.id)

    if doc is None:
        await message.reply_text(
            "Я не вижу документа для сводки. Пришли файл или ответь этой командой на сообщение с файлом."
        )
        return

    if doc.needs_ocr or doc.char_count == 0:
        await message.reply_text(
            f"По «{doc.file_name}» пока не могу сделать сводку — из файла не извлёкся текст "
            "(вероятно, скан; OCR подключим позже)."
        )
        return

    await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.UPLOAD_DOCUMENT)
    await message.reply_text(f"Разбираю «{doc.file_name}» и готовлю сводку, минутку…")

    try:
        result = await asyncio.to_thread(summarizer.summarize, doc)
    except Exception as e:
        logger.exception("Ошибка при формировании сводки: %s", e)
        await message.reply_text("Не получилось собрать сводку. Загляни в логи, пожалуйста.")
        return

    caption = (result.get("text_summary") or "Готова сводка по документу.")[:900]
    summary_path = result["summary_path"]
    try:
        with open(summary_path, "rb") as f:
            await message.reply_document(
                document=f, filename=Path(summary_path).name, caption=caption
            )
    except Exception as e:
        logger.exception("Ошибка отправки файла сводки: %s", e)
        await message.reply_text(caption)


async def _handle_registry_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    chat = message.chat
    registry_path = settings.DATA_DIR / "Реестр.xlsx"
    if not registry_path.exists():
        await message.reply_text(
            "Общий реестр пока пуст. Он наполняется, когда просят сводки по документам."
        )
        return
    await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.UPLOAD_DOCUMENT)
    with open(registry_path, "rb") as f:
        await message.reply_document(
            document=f, filename="Реестр.xlsx", caption="Общий реестр документов."
        )
