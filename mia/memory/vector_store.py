"""Семантическая память (RAG) на ChromaDB с эмбеддингами из Ollama.

Хранит «знания» — извлечённые факты и важные сообщения — с метаданными:
объект (чат), автор, достоверность (authoritative/likely), время.
Позволяет искать релевантное по смыслу через кроссчатовый поиск.
"""

from __future__ import annotations

import logging
from typing import Optional

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from config import settings
from mia.core import time_utils
from mia.core.llm import LLMClient, llm_client

logger = logging.getLogger(__name__)


class OllamaEmbeddingFunction(EmbeddingFunction):
    """Функция эмбеддингов Chroma, использующая модель Ollama (bge-m3)."""

    def __init__(self, client: Optional[LLMClient] = None) -> None:
        self._client = client or llm_client

    def __call__(self, input: Documents) -> Embeddings:
        return [self._client.embed(text) for text in input]


class VectorStore:
    def __init__(self, persist_dir: Optional[str] = None) -> None:
        settings.ensure_dirs()
        path = str(persist_dir or settings.CHROMA_DIR)
        self._client = chromadb.PersistentClient(path=path)
        self._collection = self._client.get_or_create_collection(
            name="mia_knowledge",
            embedding_function=OllamaEmbeddingFunction(),
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Векторная память готова: %s", path)

    def add(
        self,
        text: str,
        chat_title: str = "",
        user_id: Optional[int] = None,
        user_name: str = "",
        confidence: str = "likely",
        source_message_id: Optional[int] = None,
    ) -> str:
        """Добавляет запись в семантическую память.

        confidence: 'authoritative' (истина) или 'likely' (весьма вероятно).
        """
        doc_id = f"msg-{source_message_id}" if source_message_id else None
        if doc_id is None:
            # запасной уникальный id по времени
            doc_id = f"k-{time_utils.now().timestamp()}"

        metadata = {
            "object": chat_title or "",
            "user_id": user_id if user_id is not None else -1,
            "user_name": user_name or "",
            "confidence": confidence,
            "created_at": time_utils.iso_now(),
        }
        self._collection.upsert(ids=[doc_id], documents=[text], metadatas=[metadata])
        return doc_id

    def search(self, query: str, top_k: int = 8) -> list[dict]:
        """Кроссчатовый поиск релевантных знаний по смыслу."""
        try:
            res = self._collection.query(query_texts=[query], n_results=top_k)
        except Exception as e:
            logger.warning("Ошибка поиска в векторной памяти: %s", e)
            return []

        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        results: list[dict] = []
        for doc, meta in zip(docs, metas):
            results.append({"text": doc, "meta": meta or {}})
        return results

    def format_context(self, results: list[dict]) -> str:
        """Готовит найденные знания в текст для промпта."""
        if not results:
            return ""
        lines: list[str] = []
        for item in results:
            meta = item["meta"]
            tag = "истина" if meta.get("confidence") == "authoritative" else "вероятно"
            obj = meta.get("object") or "без объекта"
            author = meta.get("user_name") or ""
            prefix = f"[{tag}; объект: {obj}"
            if author:
                prefix += f"; от: {author}"
            prefix += "]"
            lines.append(f"{prefix} {item['text']}")
        return "\n".join(lines)

    def count(self) -> int:
        try:
            return self._collection.count()
        except Exception:
            return 0
