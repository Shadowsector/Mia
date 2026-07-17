"""Клиент локальной LLM через Ollama (чат + эмбеддинги).

Используется нативный API Ollama:
  - POST /api/chat          — генерация ответа
  - POST /api/embeddings    — эмбеддинги для памяти (RAG)

Смена модели «на лету» поддерживается: имя модели можно передать в вызов,
иначе берётся текущее значение из настроек. Позже конфигуратор сможет
переключать активную модель, меняя LLMClient.default_model.
"""

from __future__ import annotations

import logging
from typing import Optional

import requests

from config import runtime, settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Ошибка обращения к LLM."""


class LLMClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        embed_model: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.default_model = default_model or settings.LLM_MODEL
        self.embed_model = embed_model or settings.EMBED_MODEL
        self.timeout = timeout or settings.LLM_TIMEOUT

    # --- Чат ---
    def chat(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Генерирует ответ. messages — список {role, content}."""
        payload = {
            "model": model or runtime.get_active_model(),
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": (
                    temperature if temperature is not None else settings.LLM_TEMPERATURE
                ),
                "num_predict": max_tokens or settings.LLM_MAX_TOKENS,
            },
        }
        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise LLMError(f"Не удалось связаться с Ollama: {e}") from e

        if resp.status_code != 200:
            raise LLMError(f"Ollama вернул статус {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        content = (data.get("message") or {}).get("content", "")
        return content.strip()

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Упрощённый вызов: системный + пользовательский промпт."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self.chat(
            messages, model=model, temperature=temperature, max_tokens=max_tokens
        )

    # --- Vision (распознавание изображений) ---
    def chat_with_images(
        self,
        prompt: str,
        images: list[bytes],
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """Отправляет изображения (PNG/JPEG bytes) в vision-модель Ollama."""
        import base64

        encoded = [base64.b64encode(img).decode("ascii") for img in images]
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt, "images": encoded})

        payload = {
            "model": model or runtime.get_active_vision_model(),
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        try:
            resp = requests.post(
                f"{self.base_url}/api/chat", json=payload, timeout=self.timeout
            )
        except requests.RequestException as e:
            raise LLMError(f"Не удалось связаться с Ollama (vision): {e}") from e

        if resp.status_code != 200:
            raise LLMError(
                f"Ollama (vision) вернул статус {resp.status_code}: {resp.text[:200]}"
            )
        data = resp.json()
        return ((data.get("message") or {}).get("content", "")).strip()

    # --- Эмбеддинги ---
    def embed(self, text: str, model: Optional[str] = None) -> list[float]:
        payload = {"model": model or runtime.get_active_embed_model(), "prompt": text}
        try:
            resp = requests.post(
                f"{self.base_url}/api/embeddings",
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise LLMError(f"Не удалось получить эмбеддинг от Ollama: {e}") from e

        if resp.status_code != 200:
            raise LLMError(
                f"Ollama (embeddings) вернул статус {resp.status_code}: {resp.text[:200]}"
            )
        return resp.json().get("embedding", [])

    # --- Диагностика ---
    def is_available(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=10)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def list_models(self) -> list[str]:
        """Список установленных в Ollama моделей (имена тегов)."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if resp.status_code != 200:
                return []
            models = resp.json().get("models", [])
            return sorted(m.get("name", "") for m in models if m.get("name"))
        except requests.RequestException:
            return []


# Единый экземпляр клиента на приложение
llm_client = LLMClient()
