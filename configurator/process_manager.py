"""Запуск, остановка и мониторинг процесса бота Mia."""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


class BotProcessManager:
    def __init__(self) -> None:
        self._proc: Optional[subprocess.Popen] = None
        self._log_file = None

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> tuple[bool, str]:
        if self.is_running():
            return False, "Бот уже запущен."

        settings.ensure_dirs()
        stdout_path = settings.LOGS_DIR / "bot_stdout.log"
        self._log_file = open(stdout_path, "a", encoding="utf-8")

        creationflags = 0
        if sys.platform == "win32":
            # Не открывать отдельное окно консоли для дочернего процесса
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        try:
            self._proc = subprocess.Popen(
                [sys.executable, "run.py"],
                cwd=str(settings.BASE_DIR),
                stdout=self._log_file,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
            )
        except Exception as e:
            logger.exception("Не удалось запустить бота")
            return False, f"Ошибка запуска: {e}"

        time.sleep(1.5)
        if not self.is_running():
            return False, "Бот запустился и сразу завершился — проверьте логи."
        return True, f"Бот запущен (PID {self._proc.pid})."

    def stop(self, timeout: int = 10) -> tuple[bool, str]:
        if not self.is_running():
            return False, "Бот не запущен."
        assert self._proc is not None
        self._proc.terminate()
        try:
            self._proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        self._close_log()
        self._proc = None
        return True, "Бот остановлен."

    def restart(self) -> tuple[bool, str]:
        if self.is_running():
            self.stop()
            time.sleep(1)
        return self.start()

    def status_text(self) -> str:
        if self.is_running():
            assert self._proc is not None
            return f"работает (PID {self._proc.pid})"
        return "остановлен"

    def _close_log(self) -> None:
        if self._log_file:
            try:
                self._log_file.close()
            except Exception:
                pass
            self._log_file = None
