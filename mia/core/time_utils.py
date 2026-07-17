"""Понимание времени. Все времена — в часовом поясе компании (МСК по умолчанию)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from config import settings

_WEEKDAYS_RU = [
    "понедельник", "вторник", "среда", "четверг",
    "пятница", "суббота", "воскресенье",
]
_MONTHS_RU = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


def get_tz() -> ZoneInfo:
    try:
        return ZoneInfo(settings.TIMEZONE)
    except Exception:
        return ZoneInfo("Europe/Moscow")


def now() -> datetime:
    """Текущее время в часовом поясе компании."""
    return datetime.now(get_tz())


def human_now() -> str:
    """Человекочитаемая дата/время для контекста модели.

    Пример: 'понедельник, 6 июля 2026, 09:41 (МСК)'.
    """
    dt = now()
    weekday = _WEEKDAYS_RU[dt.weekday()]
    month = _MONTHS_RU[dt.month - 1]
    return f"{weekday}, {dt.day} {month} {dt.year}, {dt:%H:%M} (МСК)"


def iso_now() -> str:
    """ISO-время с зоной — для хранения в БД."""
    return now().isoformat()
