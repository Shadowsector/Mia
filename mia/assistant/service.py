"""AssistantService — оркестрация ответа Мии.

Хранение сообщений выполняет слой бота (сохраняем ВСЁ). Здесь — только
генерация ответа, когда к Мие обратились: сбор контекста из памяти +
вызов LLM с персоной.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from mia.core.llm import LLMClient, LLMError, llm_client
from mia.core.persona import build_system_prompt
from mia.documents.extractor import extract_text
from mia.memory.database import StoredDocument
from mia.memory.memory_service import MemoryService

logger = logging.getLogger(__name__)

_FALLBACK = "Извини, сейчас немного задумалась — не получилось ответить. Попробуй ещё разок чуть позже."
_DOC_MAX = 16000


class AssistantService:
    def __init__(
        self,
        memory: Optional[MemoryService] = None,
        llm: Optional[LLMClient] = None,
    ) -> None:
        self.memory = memory or MemoryService()
        self.llm = llm or llm_client

    def answer(
        self,
        text: str,
        chat_id: int,
        chat_title: str = "",
        user_id: Optional[int] = None,
    ) -> str:
        """Генерирует ответ Мии на обращение."""
        if not text or not text.strip():
            return "Я тут! Что подсказать?"

        query = text.strip()

        memory_context = self.memory.recall(query, chat_id=chat_id)
        recent = self.memory.recent_dialogue(chat_id, limit=8)

        system_prompt = build_system_prompt(
            chat_title=chat_title,
            user_id=user_id,
            memory_context=memory_context,
        )

        user_prompt = query
        if recent:
            user_prompt = (
                f"Последние сообщения в этом чате:\n{recent}\n\n"
                f"Сообщение, на которое нужно ответить:\n{query}"
            )

        try:
            return self.llm.complete(system_prompt, user_prompt)
        except LLMError as e:
            logger.error("Ошибка LLM при ответе: %s", e)
            return _FALLBACK

    def answer_about_document(
        self,
        text: str,
        doc: StoredDocument,
        chat_title: str = "",
        user_id: Optional[int] = None,
    ) -> str:
        """Отвечает на вопрос по КОНКРЕТНОМУ документу, опираясь на его текст."""
        doc_text = self._read_doc_text(doc)
        if not doc_text.strip():
            return (
                f"Файл «{doc.file_name}» я сохранила, но текст из него извлечь не удалось "
                "(похоже, это скан — распознавание подключим позже). Не могу разобрать содержимое."
            )

        system_prompt = build_system_prompt(chat_title=chat_title, user_id=user_id)
        system_prompt += (
            f"\n\nК тебе обращаются по документу «{doc.file_name}». "
            "Отвечай СТРОГО по его содержимому ниже, не выдумывай. Если в документе "
            "нужной информации нет — так и скажи.\n\n"
            f"Содержимое документа (может быть обрезано):\n{doc_text[:_DOC_MAX]}"
        )

        try:
            return self.llm.complete(system_prompt, text.strip(), max_tokens=1500)
        except LLMError as e:
            logger.error("Ошибка LLM при разборе документа: %s", e)
            return _FALLBACK

    @staticmethod
    def _read_doc_text(doc: StoredDocument) -> str:
        if doc.text_path and Path(doc.text_path).exists():
            return Path(doc.text_path).read_text(encoding="utf-8", errors="replace")
        if doc.stored_path and Path(doc.stored_path).exists():
            return extract_text(doc.stored_path).text
        return ""
