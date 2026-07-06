"""AssistantService — оркестрация ответа Мии.

Хранение сообщений выполняет слой бота (сохраняем ВСЁ). Здесь — только
генерация ответа, когда к Мие обратились: сбор контекста из памяти +
вызов LLM с персоной.
"""

from __future__ import annotations

import logging
from typing import Optional

from mia.core.llm import LLMClient, LLMError, llm_client
from mia.core.persona import build_system_prompt
from mia.memory.memory_service import MemoryService

logger = logging.getLogger(__name__)

_FALLBACK = "Извини, сейчас немного задумалась — не получилось ответить. Попробуй ещё разок чуть позже."


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
