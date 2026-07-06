"""Настройка логирования: в консоль и в файл (для конфигуратора/отправки логов)."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from config import settings


def setup_logging(level: int = logging.INFO) -> None:
    settings.ensure_dirs()

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    root = logging.getLogger()
    root.setLevel(level)

    # Чистим возможные предыдущие хендлеры (при повторном запуске)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        settings.LOGS_DIR / "mia.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Снижаем шум от сторонних библиотек
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
