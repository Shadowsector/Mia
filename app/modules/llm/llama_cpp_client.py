"""LlamaCppClient - OpenAI-совместимый клиент для llama.cpp (llama-server).

Mia PM OS использует llama.cpp (`llama-server`) вместо Ollama. Сервер поднимает
OpenAI-совместимые эндпоинты:
  - POST /v1/chat/completions
  - POST /v1/embeddings   (только если сервер запущен с флагом --embeddings)
  - GET  /v1/models

Клиент предоставляет:
  - синхронные методы (`chat`, `complete`, `get_embedding`, `is_available`,
    `list_models`) для запуска из потоков;
  - асинхронные (`generate`, `generate_json`) — совместимы по духу с
    `app.modules.llm.ollama_client.OllamaClient`, чтобы доменные модули
    (delegation, accuracy) могли работать без изменений через инъекцию.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class LlamaCppError(Exception):
    """Ошибка обращения к llama.cpp."""


def _strip_code_fence(text: str) -> str:
    """Убрать обрамление ```json ... ``` из ответа модели."""
    t = (text or "").strip()
    if t.startswith("```"):
        # снять первую строку с ``` или ```json
        newline = t.find("\n")
        t = t[newline + 1:] if newline != -1 else ""
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


class LlamaCppClient:
    """Клиент llama-server (OpenAI-compatible API)."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        embed_model: Optional[str] = None,
        timeout: Optional[int] = None,
        cache_dir: Optional[str] = None,
    ) -> None:
        from config import settings

        self.base_url = (
            base_url or getattr(settings, "LLAMA_BASE_URL", "http://localhost:8080")
        ).rstrip("/")
        self.default_model = default_model or getattr(
            settings, "LLAMA_MODEL", "qwen2.5:14b-instruct"
        )
        self.embed_model = (
            embed_model
            or getattr(settings, "LLAMA_EMBED_MODEL", "")
            or self.default_model
        )
        self.timeout = timeout or getattr(settings, "LLM_TIMEOUT", 300)

        self.cache_dir = Path(cache_dir) if cache_dir else Path("./data/llm_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ==================== Синхронный API ====================

    def chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1200,
        json_mode: bool = False,
    ) -> str:
        """Отправить сообщения в /v1/chat/completions и вернуть текст ответа."""
        payload: Dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            resp = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise LlamaCppError(f"llama.cpp недоступен: {e}") from e

        if resp.status_code != 200:
            raise LlamaCppError(
                f"llama.cpp вернул статус {resp.status_code}: {resp.text[:200]}"
            )

        data = resp.json()
        choices = data.get("choices") or [{}]
        content = (choices[0].get("message") or {}).get("content", "")
        return (content or "").strip()

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1200,
    ) -> str:
        """Упрощённый вызов: системный + пользовательский промпт."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self.chat(
            messages, model=model, temperature=temperature, max_tokens=max_tokens
        )

    def get_embedding(self, text: str, model: Optional[str] = None) -> List[float]:
        """Получить эмбеддинг. Требует llama-server с --embeddings (иначе 501)."""
        payload = {"model": model or self.embed_model, "input": text}
        try:
            resp = requests.post(
                f"{self.base_url}/v1/embeddings", json=payload, timeout=self.timeout
            )
        except requests.RequestException as e:
            raise LlamaCppError(f"llama.cpp (embeddings) недоступен: {e}") from e

        if resp.status_code != 200:
            raise LlamaCppError(
                f"llama.cpp (embeddings) вернул статус {resp.status_code}: "
                f"{resp.text[:200]}"
            )
        data = resp.json().get("data") or [{}]
        return data[0].get("embedding", []) or []

    def is_available(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/v1/models", timeout=10)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def list_models(self) -> List[str]:
        """Список моделей, которые обслуживает llama-server."""
        try:
            resp = requests.get(f"{self.base_url}/v1/models", timeout=10)
            if resp.status_code != 200:
                return []
            data = resp.json().get("data", [])
            return sorted(m.get("id", "") for m in data if m.get("id"))
        except requests.RequestException:
            return []

    # ==================== Асинхронный API (для доменных модулей) ====================

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        format_type: Optional[str] = None,
        temperature: float = 0.7,
        num_predict: int = 1000,
        cache_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Асинхронная генерация (совместима с OllamaClient.generate)."""
        if cache_key:
            cached = self._get_from_cache(cache_key)
            if cached:
                return cached

        text = await asyncio.to_thread(
            self.chat,
            [{"role": "user", "content": prompt}],
            model,
            temperature,
            num_predict,
            format_type == "json",
        )

        result: Dict[str, Any] = {"response": text, "model": model or self.default_model}
        if cache_key:
            self._save_to_cache(cache_key, result)
        return result

    async def generate_json(
        self,
        prompt: str,
        model: Optional[str] = None,
        schema_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Асинхронная генерация с парсингом JSON (совместима с OllamaClient)."""
        if schema_hint:
            prompt = f"{prompt}\n\nJSON Schema (strictly follow):\n{schema_hint}"

        result = await self.generate(
            prompt, model=model, format_type="json", temperature=0.3
        )
        try:
            return json.loads(_strip_code_fence(result["response"]))
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Не удалось разобрать JSON от llama.cpp: %s", e)
            return {"error": "Failed to parse JSON", "raw_response": result.get("response", "")}

    # ==================== Кэш ====================

    def _generate_cache_key(self, prompt: str, model: str, format_type: Optional[str]) -> str:
        cache_string = f"{prompt}_{model}_{format_type}"
        return hashlib.sha256(cache_string.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Cache read error: {e}")
        return None

    def _save_to_cache(self, cache_key: str, result: Dict[str, Any]) -> None:
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Cache write error: {e}")

    def clear_cache(self) -> None:
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()

    def get_cache_stats(self) -> Dict[str, Any]:
        cache_files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in cache_files)
        return {
            "cache_dir": str(self.cache_dir),
            "cached_requests": len(cache_files),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
        }
