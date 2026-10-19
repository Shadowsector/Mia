"""Tests for ObjectQueryRouter — свободные запросы по объектам."""

import uuid
from datetime import datetime

import pytest

from app.modules.storage.database import get_db_connection, initialize_database


@pytest.fixture(scope="module", autouse=True)
def db():
    initialize_database()
    yield


@pytest.fixture()
def router():
    from app.modules.object_diary.object_query import ObjectQueryRouter

    return ObjectQueryRouter()


@pytest.fixture()
def obj():
    """Создать объект с уникальным «уличным» именем + счета, ограничения, документ."""
    sfx = uuid.uuid4().hex[:8]
    oid = f"OBJ-OQ-{sfx}"
    name = f"Лодочная {sfx}"
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO objects (object_name, object_id) VALUES (?, ?)",
            (name, oid),
        )
        diary_id = cur.lastrowid
        for i, (amount, desc) in enumerate(
            [(250000.0, "Кабельные лотки"), (100000.0, "Монтаж колодцев")]
        ):
            cur.execute(
                "INSERT INTO invoices (invoice_id, object_id, amount, date, status, description) "
                "VALUES (?, ?, ?, ?, 'paid', ?)",
                (f"INV-{sfx}-{i}", oid, amount, datetime.now().date().isoformat(), desc),
            )
        for cname, status, sev in [
            ("Уведомление ОАТИ", "NOT_SATISFIED", "CRITICAL"),
            ("Разрешение на земляные работы", "NOT_SATISFIED", "MAJOR"),
            ("Согласование с УК", "SATISFIED", "MINOR"),
        ]:
            cur.execute(
                "INSERT INTO constraints (object_id, constraint_type, constraint_name, "
                "description, status, severity_level) VALUES (?, 'document', ?, ?, ?, ?)",
                (oid, cname, f"{cname} — детали", status, sev),
            )
        cur.execute(
            "INSERT INTO virtual_documents (diary_id, doc_type, doc_name, status) "
            "VALUES (?, 'permit', ?, 'MISSING')",
            (diary_id, "ОАТИ ордер"),
        )
    return {"object_id": oid, "name": name}


class TestSpend:
    def test_sum_and_count(self, router, obj):
        answer = router.query(f"Миа, сколько потрачено на {obj['name']}?")
        assert answer is not None
        assert "350 000" in answer
        assert "2" in answer
        assert "Кабельные лотки" in answer

    def test_unknown_object_returns_none(self, router):
        assert router.query("сколько потрачено по объекту Zzzzqqq") is None

    def test_no_object_returns_none(self, router):
        assert router.query("сколько потрачено?") is None


class TestPurchases:
    def test_lists_invoices(self, router, obj):
        answer = router.query(f"Миа, что мы закупили по {obj['name']}?")
        assert answer is not None
        assert "Кабельные лотки" in answer
        assert "Монтаж колодцев" in answer


class TestBlockers:
    def test_lists_active_only(self, router, obj):
        answer = router.query(f"Миа, что нас держит по {obj['name']}?")
        assert answer is not None
        assert "Уведомление ОАТИ" in answer
        assert "Разрешение на земляные работы" in answer
        assert "Согласование с УК" not in answer


class TestDocumentPresence:
    def test_finds_constraint_and_doc(self, router, obj):
        answer = router.query(f"Миа, есть ли ОАТИ по {obj['name']}?")
        assert answer is not None
        assert "ОАТИ" in answer
        assert "NOT_SATISFIED" in answer

    def test_absent_document(self, router, obj):
        answer = router.query(f"есть ли пропуск на территорию по {obj['name']}?")
        assert answer is not None
        assert "не нашла" in answer


class TestNoMatch:
    def test_general_chat_not_matched(self, router):
        assert router.query("привет, как дела?") is None

    def test_intent_without_object_not_matched(self, router):
        assert router.query("что нас держит вообще?") is None


class TestAssistantIntegration:
    def test_assistant_routes_without_llm(self, obj):
        from app.bot.assistant import PmOsAssistant

        class NoChat:
            def chat(self, *args, **kwargs):
                raise AssertionError("LLM не должен вызываться для запроса по объекту")

            def complete(self, *args, **kwargs):
                raise AssertionError("LLM не должен вызываться для запроса по объекту")

        a = PmOsAssistant(llm=NoChat(), delegation=None)
        reply = a.handle_text(f"Миа, сколько потрачено на {obj['name']}?", chat_id=1)
        assert "350 000" in reply
