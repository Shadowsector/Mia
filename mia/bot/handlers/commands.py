"""Служебные команды бота."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

_START_TEXT = (
    "Привет! Я Миа — ассистент компании.\n"
    "Я помню всё, что происходит в рабочих чатах, и помогаю с информацией по объектам.\n\n"
    "В личке отвечаю на каждое сообщение. В группах — когда обратитесь ко мне по имени "
    "(упомяните @) или ответите на моё сообщение.\n\n"
    "Команды: /help — справка, /stats — сколько я всего запомнила."
)

_HELP_TEXT = (
    "Что я умею уже сейчас:\n"
    "• Запоминаю все сообщения из чатов (даже когда молчу).\n"
    "• Отвечаю на вопросы, опираясь на память по всем объектам.\n"
    "• Понимаю, из какого чата/объекта пришла информация.\n"
    "• Принимаю и разбираю документы (docx, xlsx, pdf).\n"
    "• По просьбе делаю сводку в xlsx: «Миа, дай сводку по этому документу»\n"
    "  (ответом на файл). А «дай реестр» — пришлю общий реестр документов.\n\n"
    "Скоро добавим: голосовые (распознавание речи), OCR для сканов, напоминания."
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(_START_TEXT)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(_HELP_TEXT)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    memory = context.application.bot_data.get("memory")
    if not memory or not update.message:
        return
    stats = memory.stats()
    await update.message.reply_text(
        f"В памяти сообщений: {stats['messages']}\n"
        f"Проиндексировано знаний: {stats['knowledge']}"
    )
