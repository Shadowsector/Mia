"""Загрузка и доступ к справочнику сотрудников (config/employees.json)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class Employee:
    telegram_id: Optional[int]
    full_name: str
    position: str = ""
    mia_attitude: str = ""
    authoritative: bool = False


def _load_raw() -> list[dict]:
    try:
        with open(settings.EMPLOYEES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("employees", [])
    except FileNotFoundError:
        logger.warning("Файл сотрудников не найден: %s", settings.EMPLOYEES_FILE)
        return []
    except json.JSONDecodeError as e:
        logger.error("Ошибка чтения employees.json: %s", e)
        return []


def load_employees() -> list[Employee]:
    result: list[Employee] = []
    for item in _load_raw():
        result.append(
            Employee(
                telegram_id=item.get("telegram_id"),
                full_name=item.get("full_name", "—"),
                position=item.get("position", ""),
                mia_attitude=item.get("mia_attitude", ""),
                authoritative=bool(item.get("authoritative", False)),
            )
        )
    return result


def get_employee(telegram_id: Optional[int]) -> Optional[Employee]:
    if telegram_id is None:
        return None
    for emp in load_employees():
        if emp.telegram_id == telegram_id:
            return emp
    return None


def is_authoritative(telegram_id: Optional[int]) -> bool:
    """Является ли пользователь авторитетным источником (его слова = истина)."""
    if telegram_id is None:
        return False
    if telegram_id in settings.AUTHORITATIVE_USER_IDS:
        return True
    emp = get_employee(telegram_id)
    return bool(emp and emp.authoritative)


def describe_employees() -> str:
    """Текстовое описание сотрудников для системного промпта."""
    lines: list[str] = []
    for emp in load_employees():
        parts = [f"- {emp.full_name}"]
        if emp.position:
            parts.append(f"({emp.position})")
        if emp.mia_attitude:
            parts.append(f"— {emp.mia_attitude}")
        lines.append(" ".join(parts))
    return "\n".join(lines) if lines else "(справочник пуст)"
