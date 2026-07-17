"""Отправка логов на GitHub и локальный экспорт.

Логи публикуются в отдельную ветку репозитория (по умолчанию `mia-logs`)
через GitHub Contents API — так они не смешиваются с кодом, а разработчик
(через Cursor) может их сразу посмотреть.

Требуется GITHUB_TOKEN (Personal Access Token со scope `repo`).
"""

from __future__ import annotations

import base64
import logging
import zipfile
from pathlib import Path
from typing import Optional

import requests

from config import settings
from mia.core import time_utils

logger = logging.getLogger(__name__)

_API = "https://api.github.com"
_LOGS_BRANCH = "mia-logs"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get_default_branch_sha() -> Optional[str]:
    repo = settings.GITHUB_REPO
    r = requests.get(f"{_API}/repos/{repo}", headers=_headers(), timeout=30)
    if r.status_code != 200:
        return None
    default = r.json().get("default_branch", "main")
    r2 = requests.get(
        f"{_API}/repos/{repo}/git/refs/heads/{default}", headers=_headers(), timeout=30
    )
    if r2.status_code != 200:
        return None
    return r2.json()["object"]["sha"]


def _ensure_logs_branch() -> tuple[bool, str]:
    repo = settings.GITHUB_REPO
    r = requests.get(
        f"{_API}/repos/{repo}/git/refs/heads/{_LOGS_BRANCH}",
        headers=_headers(),
        timeout=30,
    )
    if r.status_code == 200:
        return True, "ok"
    base_sha = _get_default_branch_sha()
    if not base_sha:
        return False, "Не удалось определить базовую ветку репозитория."
    r2 = requests.post(
        f"{_API}/repos/{repo}/git/refs",
        headers=_headers(),
        json={"ref": f"refs/heads/{_LOGS_BRANCH}", "sha": base_sha},
        timeout=30,
    )
    if r2.status_code in (200, 201):
        return True, "created"
    return False, f"Не удалось создать ветку логов: {r2.status_code} {r2.text[:200]}"


def _collect_log_text(max_bytes: int = 400_000) -> str:
    log_path = settings.LOGS_DIR / "mia.log"
    if not log_path.exists():
        return ""
    data = log_path.read_bytes()
    if len(data) > max_bytes:
        data = data[-max_bytes:]
    return data.decode("utf-8", errors="replace")


def send_logs_to_github() -> tuple[bool, str]:
    if not settings.GITHUB_TOKEN:
        return False, "GITHUB_TOKEN не задан в .env — отправка логов недоступна."

    text = _collect_log_text()
    if not text.strip():
        return False, "Логи пусты — нечего отправлять."

    ok, msg = _ensure_logs_branch()
    if not ok:
        return False, msg

    repo = settings.GITHUB_REPO
    ts = time_utils.now().strftime("%Y%m%d-%H%M%S")
    path = f"logs/mia-{ts}.log"
    payload = {
        "message": f"Логи Mia {ts}",
        "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
        "branch": _LOGS_BRANCH,
    }
    r = requests.put(
        f"{_API}/repos/{repo}/contents/{path}",
        headers=_headers(),
        json=payload,
        timeout=60,
    )
    if r.status_code in (200, 201):
        url = r.json().get("content", {}).get("html_url", "")
        return True, f"Логи отправлены: {url or path}"
    return False, f"Ошибка отправки: {r.status_code} {r.text[:200]}"


def send_file_to_github(local_path: str) -> tuple[bool, str]:
    """Загружает произвольный файл (например, документ для разработчика)
    в ветку mia-logs, папка shared/. Файл именуется с меткой времени, чтобы
    не конфликтовать с существующими."""
    if not settings.GITHUB_TOKEN:
        return False, "GITHUB_TOKEN не задан в .env — отправка файлов недоступна."

    src = Path(local_path)
    if not src.exists() or not src.is_file():
        return False, "Файл не найден."

    # Ограничение Contents API — около 100 МБ, но разумно держать до ~25 МБ.
    size_mb = src.stat().st_size / (1024 * 1024)
    if size_mb > 25:
        return False, f"Файл слишком большой ({size_mb:.1f} МБ). До 25 МБ."

    ok, msg = _ensure_logs_branch()
    if not ok:
        return False, msg

    repo = settings.GITHUB_REPO
    ts = time_utils.now().strftime("%Y%m%d-%H%M%S")
    safe = src.name.replace(" ", "_")
    path = f"shared/{ts}_{safe}"
    content = base64.b64encode(src.read_bytes()).decode("ascii")
    payload = {
        "message": f"Файл для разработчика: {src.name}",
        "content": content,
        "branch": _LOGS_BRANCH,
    }
    r = requests.put(
        f"{_API}/repos/{repo}/contents/{path}",
        headers=_headers(),
        json=payload,
        timeout=120,
    )
    if r.status_code in (200, 201):
        url = r.json().get("content", {}).get("html_url", "")
        return True, f"Файл отправлен: {url or path}"
    return False, f"Ошибка отправки: {r.status_code} {r.text[:200]}"


def export_logs_zip(dest_path: str) -> tuple[bool, str]:
    """Собирает все логи в zip-архив (локально)."""
    logs_dir = settings.LOGS_DIR
    if not logs_dir.exists() or not any(logs_dir.iterdir()):
        return False, "Папка логов пуста."
    dest = Path(dest_path)
    try:
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in logs_dir.glob("*"):
                if file.is_file():
                    zf.write(file, arcname=file.name)
    except Exception as e:
        return False, f"Ошибка экспорта: {e}"
    return True, f"Логи сохранены: {dest}"
