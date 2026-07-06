"""Клиент AnythingLLM: загрузка документов в RAG и вопросы по базе документов.

Используется как «движок понимания текста» для свободных вопросов по всей базе
документов. Точные числа из таблиц считает наш код, а не RAG.

Если AnythingLLM не настроен/недоступен — все методы деградируют мягко
(is_available() == False), и бот продолжает работать на своей памяти.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import requests

from config import settings

logger = logging.getLogger(__name__)


class AnythingLLMClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        workspace: Optional[str] = None,
        timeout: int = 300,
    ) -> None:
        self.base_url = (base_url or settings.ANYTHINGLLM_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.ANYTHINGLLM_API_KEY
        self.workspace = workspace or settings.ANYTHINGLLM_WORKSPACE
        self.timeout = timeout

    # --- Служебное ---
    def _headers(self, json: bool = True) -> dict:
        h = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        if json:
            h["Content-Type"] = "application/json"
        return h

    def _url(self, path: str) -> str:
        return f"{self.base_url}/api/v1{path}"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def is_available(self) -> bool:
        if not self.is_configured():
            return False
        try:
            r = requests.get(self._url("/auth"), headers=self._headers(), timeout=10)
            return r.status_code == 200
        except requests.RequestException:
            return False

    # --- Workspace ---
    def ensure_workspace(self) -> bool:
        """Создаёт workspace, если его ещё нет."""
        try:
            r = requests.get(self._url("/workspaces"), headers=self._headers(), timeout=15)
            if r.status_code == 200:
                slugs = {w.get("slug") for w in r.json().get("workspaces", [])}
                if self.workspace in slugs:
                    return True
            r2 = requests.post(
                self._url("/workspace/new"),
                headers=self._headers(),
                json={"name": self.workspace},
                timeout=30,
            )
            if r2.status_code in (200, 201):
                slug = (r2.json().get("workspace") or {}).get("slug")
                if slug:
                    self.workspace = slug
                return True
        except requests.RequestException as e:
            logger.warning("AnythingLLM ensure_workspace: %s", e)
        return False

    # --- Документы ---
    def upload_and_embed(self, file_path: str) -> bool:
        """Загружает файл в AnythingLLM и добавляет его в workspace (RAG)."""
        if not self.is_configured():
            return False
        path = Path(file_path)
        if not path.exists():
            return False
        try:
            with open(path, "rb") as f:
                up = requests.post(
                    self._url("/document/upload"),
                    headers=self._headers(json=False),
                    files={"file": (path.name, f)},
                    timeout=self.timeout,
                )
            if up.status_code not in (200, 201):
                logger.warning("AnythingLLM upload: статус %s: %s", up.status_code, up.text[:200])
                return False
            docs = up.json().get("documents", [])
            locations = [d.get("location") for d in docs if d.get("location")]
            if not locations:
                return False

            emb = requests.post(
                self._url(f"/workspace/{self.workspace}/update-embeddings"),
                headers=self._headers(),
                json={"adds": locations, "deletes": []},
                timeout=self.timeout,
            )
            return emb.status_code in (200, 201)
        except requests.RequestException as e:
            logger.warning("AnythingLLM upload_and_embed: %s", e)
            return False

    # --- Вопросы (RAG) ---
    def query(self, message: str, mode: str = "query") -> Optional[dict]:
        """Задаёт вопрос по базе документов. Возвращает {text, sources} или None."""
        if not self.is_configured():
            return None
        try:
            r = requests.post(
                self._url(f"/workspace/{self.workspace}/chat"),
                headers=self._headers(),
                json={"message": message, "mode": mode},
                timeout=self.timeout,
            )
            if r.status_code != 200:
                logger.warning("AnythingLLM chat: статус %s: %s", r.status_code, r.text[:200])
                return None
            data = r.json()
            return {
                "text": data.get("textResponse", "") or "",
                "sources": data.get("sources", []) or [],
            }
        except requests.RequestException as e:
            logger.warning("AnythingLLM query: %s", e)
            return None


anythingllm_client = AnythingLLMClient()
