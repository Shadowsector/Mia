"""Приём документов и голосовых.

Документы принимаются молча: скачиваются, из них извлекается текст, всё
сохраняется в память. Сводка формируется ОТДЕЛЬНО и только по запросу
(«Миа, дай сводку по этому документу») — см. handlers/messages.py.

Голосовые (STT) и OCR для сканов — следующий этап.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from config import settings
from mia.documents.extractor import extract_text

logger = logging.getLogger(__name__)


def _safe_filename(name: str, unique: str) -> str:
    stem = Path(name).stem
    ext = Path(name).suffix
    stem = re.sub(r"[^\w.\- ]", "_", stem, flags=re.UNICODE).strip() or "file"
    return f"{stem}_{unique}{ext}"


def _process_document(stored_path: Path, file_name: str) -> dict:
    """Блокирующая часть: извлечь текст и сохранить его рядом. Возвращает метаданные."""
    result = extract_text(stored_path)
    text_path = ""
    if result.has_text:
        text_path = str(stored_path.with_suffix(stored_path.suffix + ".txt"))
        Path(text_path).write_text(result.text, encoding="utf-8")
    return {
        "kind": result.kind,
        "needs_ocr": result.needs_ocr,
        "note": result.note,
        "char_count": len(result.text or ""),
        "text_path": text_path,
        "excerpt": (result.text or "")[:400],
    }


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.document:
        return

    doc = message.document
    chat = message.chat
    user = message.from_user
    chat_title = chat.title or (user.full_name if user else "Личный чат")

    db = context.application.bot_data["db"]
    memory = context.application.bot_data["memory"]

    settings.ensure_dirs()
    file_name = doc.file_name or f"file_{doc.file_unique_id}"
    stored_path = settings.UPLOADS_DIR / _safe_filename(file_name, doc.file_unique_id)

    try:
        tg_file = await context.bot.get_file(doc.file_id)
        await tg_file.download_to_drive(custom_path=str(stored_path))
    except Exception as e:
        logger.exception("Не удалось скачать документ: %s", e)
        await message.reply_text("Не смогла скачать файл, попробуй прислать ещё раз.")
        return

    meta = await asyncio.to_thread(_process_document, stored_path, file_name)

    db.add_document(
        chat_id=chat.id,
        file_name=file_name,
        stored_path=str(stored_path),
        text_path=meta["text_path"],
        chat_title=chat_title,
        user_id=user.id if user else None,
        user_name=(user.full_name if user else ""),
        mime=doc.mime_type or "",
        kind=meta["kind"],
        needs_ocr=meta["needs_ocr"],
        char_count=meta["char_count"],
        telegram_message_id=message.message_id,
    )

    # Заметка в память, чтобы «какие документы приходили» искалось по смыслу.
    note = f"[документ: {file_name}]"
    if meta["excerpt"].strip():
        note += f" {meta['excerpt'].strip()}"
    await asyncio.to_thread(
        memory.remember_message,
        chat_id=chat.id,
        text=note,
        chat_title=chat_title,
        user_id=user.id if user else None,
        user_name=(user.full_name if user else ""),
        msg_type="document",
        telegram_message_id=message.message_id,
    )

    if meta["needs_ocr"]:
        await message.reply_text(
            f"Приняла «{file_name}». Похоже, это скан без текста — распознавание (OCR) "
            "подключим позже. Файл я сохранила."
        )
    elif meta["char_count"] == 0:
        await message.reply_text(
            f"Приняла «{file_name}», но не смогла извлечь текст ({meta['note'] or 'формат не поддержан'})."
        )
    else:
        await message.reply_text(
            f"Приняла и разобрала «{file_name}». Если нужна сводка — напиши "
            "«Миа, дай сводку по этому документу» (ответом на файл)."
        )


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return
    await message.reply_text(
        "Голосовые я пока не расшифровываю — скоро прикрутим распознавание речи. "
        "Можешь пока написать текстом?"
    )
