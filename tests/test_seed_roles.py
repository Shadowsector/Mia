"""Tests for seed_roles_from_employees."""

import json

import pytest

from app.modules.storage.database import get_db_connection, initialize_database


@pytest.fixture(scope="module", autouse=True)
def db():
    initialize_database()
    yield


FAKE_IDS = ["900000001", "900000002"]


@pytest.fixture()
def employees_file(tmp_path):
    path = tmp_path / "employees.json"
    path.write_text(
        json.dumps(
            {
                "employees": [
                    {"telegram_id": 900000001, "full_name": "Тестов Тест", "position": "Инженер"},
                    {"telegram_id": 900000002, "full_name": "Второй Сотрудник", "position": ""},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    yield path
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM system_roles WHERE user_id IN (?, ?)", tuple(FAKE_IDS)
        )
        conn.commit()


def test_seed_inserts_employees(employees_file):
    from app.modules.storage.seed_roles import seed_roles_from_employees

    inserted = seed_roles_from_employees(employees_file)
    assert inserted == 2

    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT username, role FROM system_roles WHERE user_id = ?", ("900000001",))
        row = cur.fetchone()
    assert row["username"] == "Тестов Тест"
    assert row["role"] == "Инженер"


def test_seed_is_idempotent(employees_file):
    from app.modules.storage.seed_roles import seed_roles_from_employees

    seed_roles_from_employees(employees_file)
    assert seed_roles_from_employees(employees_file) == 0


def test_seed_missing_file_returns_zero(tmp_path):
    from app.modules.storage.seed_roles import seed_roles_from_employees

    assert seed_roles_from_employees(tmp_path / "nope.json") == 0


def test_seed_empty_position_defaults(employees_file):
    from app.modules.storage.seed_roles import seed_roles_from_employees

    seed_roles_from_employees(employees_file)
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT role FROM system_roles WHERE user_id = ?", ("900000002",))
        assert cur.fetchone()["role"] == "сотрудник"
