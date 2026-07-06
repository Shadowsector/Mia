"""Сервис памяти: объединяет постоянный лог (SQLite) и семантику (Chroma).

Принцип: сохраняем ВСЁ. Каждое сообщение попадает в лог; содержательные
сообщения дополнительно индексируются для смыслового поиска.
"""

from __future__ import annotations

import logging
from typing import Optional

from mia.core.employees import get_employee, is_authoritative
from mia.memory.database import Database
from mia.memory.vector_store import VectorStore

logger = logging.getLogger(__name__)

# Минимальная длина, чтобы индексировать сообщение в семантическую память
# (чтобы не засорять «ок», «да», «спасибо» и т.п.).
_MIN_INDEX_LEN = 12


class MemoryService:
    def __init__(
        self,
        db: Optional[Database] = None,
        vector_store: Optional[VectorStore] = None,
    ) -> None:
        self.db = db or Database()
        self.vector = vector_store or VectorStore()

    def remember_message(
        self,
        chat_id: int,
        text: str,
        chat_title: str = "",
        user_id: Optional[int] = None,
        user_name: str = "",
        msg_type: str = "text",
        telegram_message_id: Optional[int] = None,
    ) -> None:
        """Сохраняет сообщение в лог и (если содержательное) в семантику."""
        if not text or not text.strip():
            return

        authoritative = is_authoritative(user_id)

        msg_id = self.db.add_message(
            chat_id=chat_id,
            text=text,
            chat_title=chat_title,
            user_id=user_id,
            user_name=user_name,
            msg_type=msg_type,
            telegram_message_id=telegram_message_id,
            is_authoritative=authoritative,
        )

        if len(text.strip()) >= _MIN_INDEX_LEN:
            try:
                self.vector.add(
                    text=text.strip(),
                    chat_title=chat_title,
                    user_id=user_id,
                    user_name=user_name,
                    confidence="authoritative" if authoritative else "likely",
                    source_message_id=msg_id,
                )
            except Exception as e:
                # Память в лог уже записана; семантику не роняем весь поток
                logger.warning("Не удалось проиндексировать сообщение: %s", e)

    def recall(self, query: str, chat_id: int, top_k: int = 8) -> str:
        """Собирает контекст: релевантные знания (кроссчат) для ответа."""
        results = self.vector.search(query, top_k=top_k)
        return self.vector.format_context(results)

    def recent_dialogue(self, chat_id: int, limit: int = 8) -> str:
        """Короткий контекст последних сообщений этого чата."""
        messages = self.db.recent_messages(chat_id, limit=limit)
        if not messages:
            return ""
        lines = []
        for m in messages:
            who = m.user_name or "аноним"
            lines.append(f"{who}: {m.text}")
        return "\n".join(lines)

    def stats(self) -> dict:
        return {
            "messages": self.db.count_messages(),
            "knowledge": self.vector.count(),
        }
