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
from typing import Optional

from telegram import Message, Update
from telegram.ext import ContextTypes

from config import settings
from mia.documents.extractor import extract_text
from mia.memory.database import StoredDocument
from mia.rag.anythingllm import anythingllm_client

logger = logging.getLogger(__name__)


def _push_to_rag(stored_path: str) -> None:
    """Best-effort: добавить документ в базу AnythingLLM (RAG)."""
    try:
        if not anythingllm_client.is_configured():
            return
        anythingllm_client.ensure_workspace()
        ok = anythingllm_client.upload_and_embed(stored_path)
        if ok:
            logger.info("Документ добавлен в RAG (AnythingLLM): %s", stored_path)
    except Exception as e:  # noqa: BLE001
        logger.warning("Не удалось добавить документ в RAG: %s", e)


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


async def ingest_document(
    message: Message, context: ContextTypes.DEFAULT_TYPE
) -> Optional[StoredDocument]:
    """Скачивает, разбирает и сохраняет документ из сообщения. Ничего не пишет
    в чат — только возвращает сохранённый документ (или None)."""
    if not message or not message.document:
        return None

    doc = message.document
    chat = message.chat
    user = message.from_user
    chat_title = chat.title or (user.full_name if user else "Личный чат")

    db = context.application.bot_data["db"]
    memory = context.application.bot_data["memory"]

    # Уже сохраняли этот документ (по сообщению)? Вернём его.
    existing = db.get_document_by_tg_message(chat.id, message.message_id)
    if existing is not None:
        return existing

    settings.ensure_dirs()
    file_name = doc.file_name or f"file_{doc.file_unique_id}"
    stored_path = settings.UPLOADS_DIR / _safe_filename(file_name, doc.file_unique_id)

    tg_file = await context.bot.get_file(doc.file_id)
    await tg_file.download_to_drive(custom_path=str(stored_path))

    meta = await asyncio.to_thread(_process_document, stored_path, file_name)

    doc_id = db.add_document(
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

    # В фоне отправляем документ в RAG (AnythingLLM), если он есть текст.
    if meta["char_count"] > 0:
        asyncio.create_task(asyncio.to_thread(_push_to_rag, str(stored_path)))

    return db.get_document(doc_id)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.document:
        return

    file_name = message.document.file_name or "файл"
    try:
        stored = await ingest_document(message, context)
    except Exception as e:
        logger.exception("Не удалось принять документ: %s", e)
        await message.reply_text("Не смогла скачать/разобрать файл, попробуй прислать ещё раз.")
        return

    if stored is None:
        await message.reply_text("Не смогла обработать файл.")
        return

    if stored.needs_ocr:
        await message.reply_text(
            f"Приняла «{stored.file_name}» — похоже, это скан. Распознаю текст, когда "
            "попросишь сводку или зададашь вопрос по нему."
        )
    elif stored.char_count == 0:
        await message.reply_text(
            f"Приняла «{stored.file_name}», но не смогла извлечь текст "
            "(формат пока не поддерживается)."
        )
    else:
        await message.reply_text(
            f"Приняла и разобрала «{stored.file_name}». Если нужна сводка — напиши "
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
