"""Tests for the de-stubbed integrations (item 2).

Covers DelegationEngine LLM/Telegram wiring, AccuracyContour method 2/3,
temporal AlertDispatcher, TemporalAlertIntegration and the financial ledger
local/HTTP sources. All external systems are faked; nothing hits the network.
"""

import asyncio
import uuid
from datetime import datetime, timedelta, time
from types import SimpleNamespace

import pytest

from app.modules.storage.database import initialize_database, get_db_connection


@pytest.fixture(scope="module", autouse=True)
def db():
    initialize_database()
    yield


@pytest.fixture()
def suffix():
    s = uuid.uuid4().hex[:8]
    yield s
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM questions_gateway WHERE question_id LIKE 'DELEG-%'")
        cur.execute("DELETE FROM delegated_questions WHERE assigned_user_id LIKE ?", (f"U-INT-{s}%",))
        cur.execute("DELETE FROM invoices WHERE object_id LIKE ?", (f"OBJ-{s}%",))


class FakeLLM:
    """Async OllamaClient stand-in returning a canned JSON payload."""

    def __init__(self, payload):
        self.payload = payload

    async def generate_json(self, prompt, model=None):
        return self.payload


class FakeSender:
    def __init__(self, private=False, ok=True):
        self.sent = []
        self.private = private
        self.ok = ok

    def can_send_private(self, user_id):
        return self.private

    def send(self, recipient_id, text):
        self.sent.append((recipient_id, text))
        return self.ok


class FakeHealth:
    def __init__(self, scores=None, critical=None):
        self.scores = scores or {}
        self.critical = critical or []

    def calculate_all_scores(self):
        return self.scores

    def get_critical_objects(self, threshold=60):
        return self.critical


# ==================== DelegationEngine ====================


class TestDelegationEngineIntegration:
    def test_parse_with_llm(self):
        from app.modules.delegation.delegation_engine import DelegationEngine

        llm = FakeLLM({
            "is_delegation": True,
            "target_name": "Игорь",
            "question": "Когда будет акт?",
            "object_id": "OBJ-77",
            "requester_id": "denis",
        })
        engine = DelegationEngine(llm_client=llm, model="test")
        request = engine.parse_delegation_request("уточни у Игоря", "OBJ-1")

        assert request.target_name == "Игорь"
        assert request.question_context == "Когда будет акт?"
        assert request.object_id == "OBJ-77"
        assert request.requester_id == "denis"

    def test_parse_non_delegation_falls_back(self):
        from app.modules.delegation.delegation_engine import DelegationEngine

        engine = DelegationEngine(llm_client=FakeLLM({"is_delegation": False}), model="test")
        request = engine.parse_delegation_request("привет", "OBJ-1")

        assert request.target_name == "Света"
        assert request.question_context == "привет"
        assert request.object_id == "OBJ-1"

    def test_llm_failure_falls_back(self):
        from app.modules.delegation.delegation_engine import DelegationEngine

        class BrokenLLM:
            async def generate_json(self, prompt, model=None):
                raise RuntimeError("ollama down")

        engine = DelegationEngine(llm_client=BrokenLLM(), model="test")
        request = engine.parse_delegation_request("вопрос", "OBJ-2")
        assert request.target_name == "Света"

    def test_choose_channel_private_when_connected(self):
        from app.modules.delegation.delegation_engine import DelegationEngine

        engine = DelegationEngine(telegram_sender=FakeSender(private=True))
        assert engine._choose_communication_channel({"user_id": "u1"}) == "PRIVATE"

    def test_choose_channel_public_without_sender(self):
        from app.modules.delegation.delegation_engine import DelegationEngine

        engine = DelegationEngine()
        assert engine._choose_communication_channel({"user_id": "u1"}) == "PUBLIC"

    def test_delegate_uses_telegram_sender(self, suffix):
        from app.modules.delegation.delegation_engine import DelegationEngine

        sender = FakeSender()
        engine = DelegationEngine(telegram_sender=sender)
        request = engine.parse_delegation_request("Вопрос", f"OBJ-{suffix}")
        user = {"user_id": f"U-INT-{suffix}-1", "username": "Света", "role": "PURCHASING"}

        question_id = engine.delegate_question(request, user)

        assert question_id > 0
        assert sender.sent and sender.sent[0][0] == user["user_id"]
        assert sender.sent[0][1].startswith("@Света ")

        pending = engine.get_pending_questions(user["user_id"])
        assert pending[0]["message_sent"] == 1

    def test_delegate_marks_unsent_when_sender_fails(self, suffix):
        from app.modules.delegation.delegation_engine import DelegationEngine

        engine = DelegationEngine(telegram_sender=FakeSender(ok=False))
        request = engine.parse_delegation_request("Вопрос", f"OBJ-{suffix}")
        user = {"user_id": f"U-INT-{suffix}-2", "username": "Света", "role": "LEGAL"}

        question_id = engine.delegate_question(request, user)
        pending = engine.get_pending_questions(user["user_id"])
        assert pending[0]["message_sent"] == 0

    def test_intercept_answer_rejects_chatter(self):
        from app.modules.delegation.delegation_engine import DelegationEngine

        engine = DelegationEngine(llm_client=FakeLLM({"is_answer": False}), model="test")
        assert engine.intercept_answer("ахахах", 1) is False

    def test_resolve_ambiguous_creates_inbox_task(self, suffix):
        from app.modules.delegation.delegation_engine import DelegationEngine

        engine = DelegationEngine()
        candidates = [
            {"user_id": f"U-INT-{suffix}-1", "username": "Света"},
            {"user_id": f"U-INT-{suffix}-2", "username": "Светлана"},
        ]
        assert engine.resolve_ambiguous_user(candidates, f"OBJ-{suffix}") is None

        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT * FROM questions_gateway WHERE question_type = ? AND project_id = ?",
                ("DELEGATION_DISAMBIGUATION", f"OBJ-{suffix}"),
            ).fetchone()
        assert row is not None
        assert row["option_a"] == "Света"
        assert row["option_b"] == "Светлана"

    def test_escalation_sends_to_admin(self, suffix):
        from app.modules.delegation.delegation_engine import DelegationEngine

        sender = FakeSender()
        engine = DelegationEngine(telegram_sender=sender, admin_user_id="denis")

        with get_db_connection() as conn:
            conn.cursor().execute(
                "INSERT INTO delegated_questions (original_request_id, assigned_user_id, "
                "assigned_user_role, communication_channel, deadline_for_reply, escalation_status) "
                "VALUES (?,?,?,?,?,?)",
                (0, f"U-INT-{suffix}", "LEGAL", "PUBLIC",
                 (datetime.now() - timedelta(hours=30)).isoformat(), "NONE"),
            )

        escalated = engine.check_escalation()
        assert any(q["assigned_user_id"] == f"U-INT-{suffix}" for q in escalated)
        assert sender.sent and sender.sent[0][0] == "denis"


# ==================== AccuracyContour Methods 2/3 ====================


class TestAccuracyContourIntegration:
    def test_method2_detects_amount_mismatch(self):
        from app.modules.accuracy.accuracy_contour import AccuracyContourManager, CheckStatus

        class FakeRAG:
            def search_between_objects(self, query, n_results=3):
                return {"documents": [["Сумма 100000 руб, дата 01.02.2024"]]}

        manager = AccuracyContourManager()
        result = manager.method2_rag_check(
            "Сумма 999999 руб, дата 01.02.2024", ["КП"], FakeRAG()
        )

        assert result.status == CheckStatus.WARNING
        assert any(a["type"] == "amount_mismatch" for a in result.anomalies)
        assert 0.0 < result.confidence <= 0.95

    def test_method2_without_rag_falls_back(self):
        from app.modules.accuracy.accuracy_contour import AccuracyContourManager, CheckStatus

        manager = AccuracyContourManager()
        result = manager.method2_rag_check("спецификация", ["ref"], rag_manager=object())
        assert result.status == CheckStatus.OK
        assert result.confidence == 0.8

    def test_method3_llm_extracts_informal_deadlines(self):
        from app.modules.accuracy.accuracy_contour import AccuracyContourManager, CheckStatus

        llm = FakeLLM({
            "informal_deadlines": [
                {"description": "перенесли работы", "raw_text": "перенесли на 05.03.2024",
                 "date": "05.03.2024", "type": "deadline", "confidence": 0.9}
            ]
        })
        manager = AccuracyContourManager(llm_client=llm, model="test")
        result = manager.method3_telegram_check(
            [{"text": "перенесли на 05.03.2024"}],
            [{"text": "официальная дата 01.03.2024"}],
        )

        assert len(result.informal_deadlines) == 1
        assert result.status == CheckStatus.WARNING
        assert result.bypass_strict_rule is True

    def test_method3_no_llm_falls_back(self):
        from app.modules.accuracy.accuracy_contour import AccuracyContourManager, CheckStatus

        manager = AccuracyContourManager()
        result = manager.method3_telegram_check([{"text": "начнём завтра"}], [])
        assert result.status == CheckStatus.OK
        assert result.informal_deadlines == []


# ==================== AlertDispatcher ====================


class TestAlertDispatcherIntegration:
    def test_critical_alerts_dispatch(self, monkeypatch):
        from app.modules.temporal.alert_dispatcher import AlertDispatcher

        dispatcher = AlertDispatcher(
            health_engine=FakeHealth(critical=[{"object_id": "OBJ-1", "overall_score": 80}])
        )
        calls = []
        monkeypatch.setattr(dispatcher, "_dispatch_alert",
                            lambda t, r, m: calls.append((t.value, r, m)))

        dispatcher._check_critical_alerts()

        assert calls
        assert calls[0][0] == "CRITICAL"
        assert "OBJ-1" in calls[0][2]

    def test_critical_alerts_no_engine(self):
        from app.modules.temporal.alert_dispatcher import AlertDispatcher

        dispatcher = AlertDispatcher()
        dispatcher._check_critical_alerts()

    def test_daily_digest_dispatch(self, monkeypatch):
        from app.modules.temporal.alert_dispatcher import AlertDispatcher

        dispatcher = AlertDispatcher(
            health_engine=FakeHealth(scores={
                "OBJ-1": {"zone": "red"},
                "OBJ-2": {"zone": "green"},
            })
        )
        calls = []
        monkeypatch.setattr(dispatcher, "_dispatch_alert",
                            lambda t, r, m: calls.append((t.value, m)))

        dispatcher._send_daily_digest()

        assert calls and calls[0][0] == "DAILY_DIGEST"
        assert "красная зона: 1" in calls[0][1]

    def test_check_cron_tasks(self, monkeypatch):
        from app.modules.temporal.alert_dispatcher import AlertDispatcher

        class FakeTemporal:
            def execute_cron_tasks(self):
                return [
                    {"task_id": 1, "task_text": "alert: проверить сроки"},
                    {"task_id": 2, "task_text": "обычная задача"},
                ]

        dispatcher = AlertDispatcher(temporal_manager=FakeTemporal())
        calls = []
        monkeypatch.setattr(dispatcher, "_dispatch_alert", lambda t, r, m: calls.append(m))

        dispatcher._check_cron_tasks()

        assert calls == ["alert: проверить сроки"]

    def test_send_alert_uses_telegram(self):
        from app.modules.temporal.alert_dispatcher import (
            AlertDispatcher, AlertSchema, AlertType, AlertStatus,
        )

        sender = FakeSender()
        dispatcher = AlertDispatcher(telegram_sender=sender)
        dispatcher.working_hours_start = time(0, 0)
        dispatcher.working_hours_end = time(23, 59, 59)

        alert = AlertSchema(
            alert_type=AlertType.CRITICAL,
            recipient_id="u1",
            message="hi",
            scheduled_at=datetime.now(),
        )
        alert_id = dispatcher._save_alert(alert)
        alert.alert_id = f"ALERT_{alert_id}"

        asyncio.run(dispatcher._send_alert(alert))

        assert sender.sent and sender.sent[0][0] == "u1"
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT status, sent_at FROM alert_queue WHERE alert_id = ?", (alert_id,)
            ).fetchone()
        assert row["status"] == AlertStatus.SENT.value
        assert row["sent_at"]


# ==================== TemporalAlertIntegration ====================


class TestTemporalAlertIntegrationWiring:
    def test_daily_summary_counts_events(self):
        from app.modules.temporal.temporal_alert_integration import TemporalAlertIntegration

        diary = SimpleNamespace(diary_id=1, object_id="OBJ-1")
        event = SimpleNamespace(
            event_timestamp=datetime.now(),
            event_type="document_added",
            summary="Добавлен акт",
        )

        class FakeDiaryManager:
            def get_all_diaries(self):
                return [diary]

            def get_timeline(self, diary_id, only_current=True):
                return [event]

        integration = TemporalAlertIntegration(
            health_engine=FakeHealth(scores={"OBJ-1": {"zone": "red"}}),
            diary_manager=FakeDiaryManager(),
        )
        summary = integration.generate_daily_summary()

        assert summary["total_events"] == 1
        assert summary["health_status"] == "RED"
        assert summary["alert_id"].startswith("ALERT_")

    def test_critical_report_sends_alert(self, monkeypatch):
        from app.modules.temporal.temporal_alert_integration import TemporalAlertIntegration

        integration = TemporalAlertIntegration(
            health_engine=FakeHealth(critical=[{"object_id": "OBJ-1", "overall_score": 80}])
        )
        sent = []
        monkeypatch.setattr(
            integration.alert_dispatcher,
            "send_critical_alert",
            lambda recipient_id, message: sent.append((recipient_id, message)),
        )

        report = integration.generate_critical_report()

        assert report["action_required"] is True
        assert sent and sent[0][0] == "admin"

    def test_critical_report_clean_by_default(self):
        from app.modules.temporal.temporal_alert_integration import TemporalAlertIntegration

        report = TemporalAlertIntegration().generate_critical_report()
        assert report["action_required"] is False


# ==================== Financial ledger ====================


class TestFinancialLedgerIntegration:
    def test_local_source_reads_invoices(self, suffix):
        from app.modules.financial.ledger_integration import (
            FinancialLedgerIntegration, PaymentStatus,
        )

        object_id = f"OBJ-{suffix}"
        now = datetime.now()
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO invoices (invoice_id, object_id, amount, date, status, description) "
                "VALUES (?,?,?,?,?,?)",
                (f"INV-{suffix}-1", object_id, 1000.0, now.isoformat(),
                 PaymentStatus.PAID.value, "оплачено"),
            )
            cur.execute(
                "INSERT INTO invoices (invoice_id, object_id, amount, date, status, description) "
                "VALUES (?,?,?,?,?,?)",
                (f"INV-{suffix}-2", object_id, 500.0, now.isoformat(),
                 PaymentStatus.PENDING.value, "ожидает"),
            )

        integration = FinancialLedgerIntegration(integration_type="local")
        assert integration.connect({}) is True

        start, end = now - timedelta(days=1), now + timedelta(days=1)
        payments = integration.get_payments(object_id, start, end)
        invoices = integration.get_invoices(object_id, start, end)

        assert len(payments) == 1
        assert payments[0]["invoice_id"] == f"INV-{suffix}-1"
        assert len(invoices) == 2

    def test_http_connector(self, monkeypatch):
        import requests

        from app.modules.financial.ledger_integration import FinancialLedgerIntegration

        class FakeResponse:
            def __init__(self, payload, status_code=200):
                self._payload = payload
                self.status_code = status_code

            def json(self):
                return self._payload

        def fake_get(url, params=None, headers=None, timeout=None):
            if url.endswith("/health"):
                return FakeResponse({}, 200)
            return FakeResponse({"items": [{"payment_id": "P1", "amount": 1}]})

        monkeypatch.setattr(requests, "get", fake_get)

        integration = FinancialLedgerIntegration(integration_type="1c")
        assert integration.connect({"base_url": "http://erp.local", "token": "t"}) is True

        rows = integration.get_payments("OBJ-1", datetime.now() - timedelta(days=1), datetime.now())
        assert rows and rows[0]["payment_id"] == "P1"

    def test_http_connect_requires_base_url(self):
        from app.modules.financial.ledger_integration import FinancialLedgerIntegration

        integration = FinancialLedgerIntegration(integration_type="erp")
        assert integration.connect({}) is False
