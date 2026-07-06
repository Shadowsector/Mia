"""Отслеживание единственного экземпляра бота через статус-файл с heartbeat.

Бот периодически обновляет heartbeat в data/bot_status.json. По свежести
heartbeat и конфигуратор, и сам бот понимают, запущен ли уже экземпляр —
это исключает случайный двойной запуск (и конфликт в Telegram).
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Optional

from config import settings
from mia.core import time_utils

logger = logging.getLogger(__name__)

_STATUS_PATH = settings.DATA_DIR / "bot_status.json"
# Если heartbeat старше этого числа секунд — считаем, что бот не работает.
STALE_SECONDS = 20
_HEARTBEAT_INTERVAL = 5


def _read() -> dict:
    try:
        with open(_STATUS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write(data: dict) -> None:
    settings.ensure_dirs()
    tmp = _STATUS_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    tmp.replace(_STATUS_PATH)


def read_status() -> dict:
    return _read()


def _heartbeat_age() -> Optional[float]:
    data = _read()
    hb = data.get("heartbeat_ts")
    if hb is None:
        return None
    return time.time() - float(hb)


def is_running() -> bool:
    age = _heartbeat_age()
    return age is not None and age < STALE_SECONDS


def get_pid() -> Optional[int]:
    pid = _read().get("pid")
    return int(pid) if pid else None


def mark_running(pid: int) -> None:
    _write({
        "pid": pid,
        "started_at": time_utils.iso_now(),
        "heartbeat_ts": time.time(),
    })


def heartbeat() -> None:
    data = _read()
    data["heartbeat_ts"] = time.time()
    if "pid" not in data:
        data["pid"] = os.getpid()
    _write(data)


def clear() -> None:
    try:
        _STATUS_PATH.unlink()
    except FileNotFoundError:
        pass


def start_heartbeat_thread() -> threading.Thread:
    """Запускает фоновый поток, обновляющий heartbeat, пока жив процесс."""

    def loop():
        while True:
            try:
                heartbeat()
            except Exception:
                pass
            time.sleep(_HEARTBEAT_INTERVAL)

    t = threading.Thread(target=loop, daemon=True, name="mia-heartbeat")
    t.start()
    return t
