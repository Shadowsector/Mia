"""Запуск, остановка и мониторинг процесса бота Mia.

Факт «бот работает» определяется по heartbeat-статусу (mia.core.instance),
поэтому конфигуратор корректно видит бота, даже если тот запущен другим
способом, и не допускает двойного запуска.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
from typing import Optional

from config import settings
from mia.core import instance

logger = logging.getLogger(__name__)


class BotProcessManager:
    def __init__(self) -> None:
        self._proc: Optional[subprocess.Popen] = None
        self._log_file = None

    def is_running(self) -> bool:
        if instance.is_running():
            return True
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> tuple[bool, str]:
        if self.is_running():
            return False, "Бот уже запущен."

        settings.ensure_dirs()
        stdout_path = settings.LOGS_DIR / "bot_stdout.log"
        self._log_file = open(stdout_path, "a", encoding="utf-8")

        creationflags = 0
        if sys.platform == "win32":
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

        # Ждём, пока бот зарегистрирует heartbeat (импорт зависимостей может занять время).
        for _ in range(20):
            time.sleep(0.5)
            if self._proc.poll() is not None:
                return False, "Бот запустился и сразу завершился — проверьте логи."
            if instance.is_running():
                return True, f"Бот запущен (PID {self._proc.pid})."
        return True, f"Бот запускается (PID {self._proc.pid})…"

    def stop(self, timeout: int = 10) -> tuple[bool, str]:
        # Останавливаем собственный процесс, если он наш.
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._close_log()
            self._proc = None
            instance.clear()
            return True, "Бот остановлен."

        # Иначе — пытаемся остановить по PID из статуса (бот запущен извне).
        pid = instance.get_pid()
        if instance.is_running() and pid:
            ok = self._kill_pid(pid)
            instance.clear()
            if ok:
                return True, f"Бот (PID {pid}) остановлен."
            return False, f"Не удалось остановить бота (PID {pid})."

        return False, "Бот не запущен."

    def restart(self) -> tuple[bool, str]:
        if self.is_running():
            self.stop()
            time.sleep(1.5)
        return self.start()

    def status_text(self) -> str:
        if instance.is_running():
            return f"работает (PID {instance.get_pid()})"
        if self._proc is not None and self._proc.poll() is None:
            return "запускается…"
        return "остановлен"

    @staticmethod
    def _kill_pid(pid: int) -> bool:
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F", "/T"],
                    capture_output=True,
                    timeout=15,
                )
            else:
                os.kill(pid, signal.SIGTERM)
            return True
        except Exception as e:
            logger.warning("Не удалось завершить процесс %s: %s", pid, e)
            return False

    def _close_log(self) -> None:
        if self._log_file:
            try:
                self._log_file.close()
            except Exception:
                pass
            self._log_file = None
