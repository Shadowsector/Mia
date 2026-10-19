"""Заполнение `system_roles` сотрудниками из `config/employees.json`.

`DelegationEngine.find_user_by_name` ищет людей в таблице `system_roles`
(столбцы `user_id`, `username`, `role`). Этот модуль переносит туда данные из
редактируемого файла сотрудников (idempotent — повторный запуск не дублирует).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.modules.storage.database import get_db_connection, initialize_database

logger = logging.getLogger(__name__)

DEFAULT_EMPLOYEES_FILE = Path(__file__).resolve().parents[3] / "config" / "employees.json"


def _load_employees(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data.get("employees", []) or []
    return data or []


def seed_roles_from_employees(path: Optional[Path] = None) -> int:
    """Вставить сотрудников в `system_roles`. Возвращает число новых записей."""
    path = Path(path) if path else DEFAULT_EMPLOYEES_FILE
    if not path.exists():
        logger.warning("Файл сотрудников не найден: %s", path)
        return 0

    employees = _load_employees(path)
    inserted = 0

    with get_db_connection() as conn:
        cursor = conn.cursor()
        for emp in employees:
            telegram_id = emp.get("telegram_id")
            full_name = (emp.get("full_name") or "").strip()
            position = (emp.get("position") or "").strip()
            if telegram_id is None or not full_name:
                continue

            user_id = str(telegram_id)
            cursor.execute(
                "SELECT role_id FROM system_roles WHERE user_id = ?", (user_id,)
            )
            if cursor.fetchone():
                continue

            cursor.execute(
                """
                INSERT INTO system_roles (user_id, username, role, object_id, capabilities)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, full_name, position or "сотрудник", None, "[]"),
            )
            inserted += 1

        conn.commit()

    logger.info("system_roles: добавлено сотрудников — %s", inserted)
    return inserted


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    initialize_database()
    count = seed_roles_from_employees()
    print(f"Добавлено сотрудников: {count}")


if __name__ == "__main__":
    main()
