"""Runtime-настройки, изменяемые «на лету» (конфигуратором), без перезапуска.

Хранятся в JSON внутри DATA_DIR. Бот читает активную модель отсюда при каждом
обращении, поэтому конфигуратор может переключить модель (например, ночью — на
тяжёлую vision-модель), и бот подхватит без рестарта.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Optional

from config import settings

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_RUNTIME_PATH = settings.DATA_DIR / "runtime.json"


def _read() -> dict:
    try:
        with open(_RUNTIME_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        logger.warning("runtime.json повреждён: %s", e)
        return {}


def _write(data: dict) -> None:
    settings.ensure_dirs()
    tmp = _RUNTIME_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(_RUNTIME_PATH)


def get(key: str, default: Any = None) -> Any:
    with _LOCK:
        return _read().get(key, default)


def set_value(key: str, value: Any) -> None:
    with _LOCK:
        data = _read()
        data[key] = value
        _write(data)
    logger.info("Runtime-настройка обновлена: %s = %s", key, value)


def all_values() -> dict:
    with _LOCK:
        return _read()


def get_active_model() -> str:
    """Активная модель чата: runtime-переопределение или значение из .env."""
    return get("active_model") or settings.LLM_MODEL


def get_active_embed_model() -> str:
    return get("active_embed_model") or settings.EMBED_MODEL


def set_active_model(model: str) -> None:
    set_value("active_model", model)


def set_active_embed_model(model: str) -> None:
    set_value("active_embed_model", model)
