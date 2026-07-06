"""Автообновление из GitHub через git.

Логика надёжного апдейта для не-разработчика:
  - проверяем, что это git-репозиторий;
  - git fetch нужной ветки;
  - сравниваем локальный HEAD с origin/<branch>;
  - применяем обновление через reset --hard на origin/<branch>.

Данные (data/) и .env в .gitignore, поэтому обновление кода их не затрагивает.
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

_GIT_TIMEOUT = 120


@dataclass
class UpdateStatus:
    ok: bool
    has_updates: bool
    message: str
    behind: int = 0
    local_commit: str = ""
    remote_commit: str = ""


def _run_git(args: list[str], retries: int = 1) -> tuple[int, str]:
    """Запускает git в корне проекта. Возвращает (код, вывод)."""
    last_out = ""
    for attempt in range(retries):
        try:
            proc = subprocess.run(
                ["git", *args],
                cwd=str(settings.BASE_DIR),
                capture_output=True,
                text=True,
                timeout=_GIT_TIMEOUT,
            )
            out = (proc.stdout + proc.stderr).strip()
            if proc.returncode == 0:
                return 0, out
            last_out = out
        except FileNotFoundError:
            return 127, "git не найден. Установите Git и добавьте в PATH."
        except subprocess.TimeoutExpired:
            last_out = "git: превышено время ожидания"
        if attempt < retries - 1:
            time.sleep(2 * (attempt + 1))
    return 1, last_out


def is_git_repo() -> bool:
    code, _ = _run_git(["rev-parse", "--is-inside-work-tree"])
    return code == 0


def current_commit() -> str:
    code, out = _run_git(["rev-parse", "--short", "HEAD"])
    return out if code == 0 else ""


def _current_branch() -> str:
    code, out = _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    return out if code == 0 else settings.UPDATE_BRANCH


def check_for_updates(branch: Optional[str] = None) -> UpdateStatus:
    branch = branch or settings.UPDATE_BRANCH or _current_branch()

    if not is_git_repo():
        return UpdateStatus(
            ok=False,
            has_updates=False,
            message=(
                "Это не git-репозиторий. Автообновление работает только при установке "
                "через git clone. Скачайте проект командой git clone."
            ),
        )

    code, out = _run_git(["fetch", "origin", branch], retries=4)
    if code != 0:
        return UpdateStatus(False, False, f"Не удалось получить обновления: {out}")

    local = current_commit()
    code, remote = _run_git(["rev-parse", "--short", f"origin/{branch}"])
    if code != 0:
        return UpdateStatus(False, False, f"Не найдена ветка origin/{branch}: {remote}")

    code, count_out = _run_git(["rev-list", "--count", f"HEAD..origin/{branch}"])
    behind = int(count_out) if count_out.isdigit() else 0

    if behind == 0:
        return UpdateStatus(
            True, False, "У вас последняя версия.",
            behind=0, local_commit=local, remote_commit=remote,
        )
    return UpdateStatus(
        True, True,
        f"Доступно обновление: +{behind} коммит(ов) ({local} → {remote}).",
        behind=behind, local_commit=local, remote_commit=remote,
    )


def apply_update(branch: Optional[str] = None) -> UpdateStatus:
    branch = branch or settings.UPDATE_BRANCH or _current_branch()

    status = check_for_updates(branch)
    if not status.ok:
        return status
    if not status.has_updates:
        return status

    code, out = _run_git(["reset", "--hard", f"origin/{branch}"])
    if code != 0:
        return UpdateStatus(False, True, f"Ошибка применения обновления: {out}")

    new_commit = current_commit()
    return UpdateStatus(
        True, False,
        f"Обновление применено. Текущая версия: {new_commit}. "
        "Перезапустите бота, чтобы изменения вступили в силу.",
        local_commit=new_commit,
    )
