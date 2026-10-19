"""Embedding-функция ChromaDB на базе llama.cpp (OpenAI-совместимый API).

Использует отдельный llama-server с флагом ``--embedding`` (по умолчанию порт
8081, модель bge-m3) и эндпоинт ``/v1/embeddings``. Реализует интерфейс
кастомной embedding-функции ChromaDB: ``__call__``, ``embed_documents``,
``embed_query`` и статический ``name()``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.modules.llm.llama_cpp_client import LlamaCppClient


class LlamaCppEmbeddingFunction:
    """ChromaDB embedding function на базе llama.cpp."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        client: Optional[LlamaCppClient] = None,
    ) -> None:
        self.client = client or LlamaCppClient(
            embed_base_url=base_url, embed_model=model
        )

    def __call__(self, input: Any) -> List[List[float]]:  # noqa: A002 (Chroma API)
        return self.embed_documents(list(input))

    def embed_documents(self, input: Any) -> List[List[float]]:  # noqa: A002
        return self.client.get_embeddings(list(input))

    def embed_query(self, input: Any) -> List[List[float]]:  # noqa: A002
        texts = input if isinstance(input, list) else [input]
        return self.client.get_embeddings(list(texts))

    @staticmethod
    def name() -> str:
        return "llama_cpp_embeddings"

    @staticmethod
    def is_legacy() -> bool:
        return False

    @classmethod
    def build_from_config(cls, config: Dict[str, Any]) -> "LlamaCppEmbeddingFunction":
        return cls(
            base_url=config.get("base_url"),
            model=config.get("model"),
        )

    def get_config(self) -> Dict[str, Any]:
        return {
            "base_url": self.client.embed_base_url,
            "model": self.client.embed_model,
        }
