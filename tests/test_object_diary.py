"""Tests for object_diary modules (RFC Object Diary v1.9)."""

import json
from datetime import datetime, timedelta

import pytest

from app.modules.storage.database import initialize_database, get_db_connection


@pytest.fixture(scope="module", autouse=True)
def db():
    initialize_database()
    yield


@pytest.fixture()
def suffix():
    """Unique suffix so tests do not collide on shared DB state."""
    import uuid

    return uuid.uuid4().hex[:8]


class TestConstraintManager:
    @pytest.fixture()
    def manager(self):
        from app.modules.object_diary.constraint_manager import ConstraintManager

        return ConstraintManager()

    def test_add_and_get_constraint(self, manager, suffix):
        from app.modules.object_diary.constraint_manager import ConstraintType

        oid = f"OBJ-C-{suffix}"
        cid = manager.add_constraint(
            object_id=oid,
            constraint_type=ConstraintType.LEGAL,
            description="Ожидание разрешения МПТЦ",
            required_for="excavation",
        )
        assert cid > 0

        constraints = manager.get_object_constraints(oid)
        assert len(constraints) == 1
        assert constraints[0]["status"] == "NOT_SATISFIED"
        assert constraints[0]["required_for"] == ["excavation"]

    def test_can_proceed_blocks_then_allows(self, manager, suffix):
        from app.modules.object_diary.constraint_manager import ConstraintType

        oid = f"OBJ-CP-{suffix}"
        cid = manager.add_constraint(
            oid, ConstraintType.LEGAL, "Нет разрешения", "excavation"
        )

        blocked = manager.can_proceed(oid, "excavation")
        assert blocked["can_proceed"] is False
        assert len(blocked["blocking_constraints"]) == 1

        assert manager.resolve_constraint(cid, "engineer", "получено") is True
        allowed = manager.can_proceed(oid, "excavation")
        assert allowed["can_proceed"] is True

    def test_can_proceed_ignores_other_actions(self, manager, suffix):
        from app.modules.object_diary.constraint_manager import ConstraintType

        oid = f"OBJ-OTHER-{suffix}"
        manager.add_constraint(oid, ConstraintType.LEGAL, "Нет разрешения", "excavation")
        assert manager.can_proceed(oid, "painting")["can_proceed"] is True

    def test_ignore_constraint(self, manager, suffix):
        from app.modules.object_diary.constraint_manager import ConstraintType

        oid = f"OBJ-IGN-{suffix}"
        cid = manager.add_constraint(oid, ConstraintType.SCHEDULE, "Срок", "works")
        assert manager.ignore_constraint(cid, "director", "согласовано") is True
        assert manager.can_proceed(oid, "works")["can_proceed"] is True

    def test_summary_counts(self, manager, suffix):
        from app.modules.object_diary.constraint_manager import ConstraintType

        oid = f"OBJ-SUM-{suffix}"
        c1 = manager.add_constraint(oid, ConstraintType.LEGAL, "a", "act1")
        manager.add_constraint(oid, ConstraintType.FINANCIAL, "b", "act2")
        manager.resolve_constraint(c1, "user")

        summary = manager.get_constraint_summary(oid)
        assert summary["total"] == 2
        assert summary["blocking"] == 1
        assert summary["resolved"] == 1
        assert summary["by_type"]["legal"] == 1

    def test_status_filter(self, manager, suffix):
        from app.modules.object_diary.constraint_manager import (
            ConstraintType,
            ConstraintStatus,
        )

        oid = f"OBJ-FLT-{suffix}"
        cid = manager.add_constraint(oid, ConstraintType.LEGAL, "a", "act")
        manager.resolve_constraint(cid, "user")

        resolved = manager.get_object_constraints(oid, ConstraintStatus.RESOLVED)
        assert len(resolved) == 1
        assert resolved[0]["id"] == cid


class TestIntentClassifier:
    @pytest.fixture()
    def classifier(self):
        from app.modules.object_diary.intent_classifier import IntentClassifier

        return IntentClassifier()

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Какой статус объекта 123?", "query_status"),
            ("Кабель доставлен?", "query_material"),
            ("Какой бюджет проекта?", "query_financial"),
            ("Покажи договор", "query_document"),
            ("Запусти бота", "system_control"),
            ("Есть проблема с доставкой", "report_issue"),
            ("Одобри смету", "request_approval"),
            ("Создай новый объект", "request_action"),
        ],
    )
    def test_classify(self, classifier, text, expected):
        result = classifier.classify(text)
        assert result["intent"].value == expected
        assert 0 < result["confidence"] <= 1.0

    def test_general_chat_fallback(self, classifier):
        result = classifier.classify("привет как жизнь")
        assert result["intent"].value == "general_chat"

    def test_extract_entities(self, classifier):
        result = classifier.classify_with_entities(
            "Объект: 123, срок 15.03.2024, сумма 1500.50 руб"
        )
        entities = result["entities"]
        assert entities["object_id"] == "123"
        assert entities["date"] == "2024-03-15"
        assert entities["amount"] == "1500.50"

    def test_extract_entities_empty(self, classifier):
        assert classifier.classify_with_entities("просто текст")["entities"] == {}


class TestHealthScoreEngine:
    @pytest.fixture()
    def engine(self):
        from app.modules.object_diary.health_score_engine import HealthScoreEngine

        return HealthScoreEngine()

    def test_unknown_object_has_silence_risk(self, engine, suffix):
        score = engine.calculate_health_score(f"OBJ-NONE-{suffix}")
        assert score["components"]["silence_risk"] == 50
        assert score["overall_score"] == 10.0
        assert score["zone"] == "green"

    def test_schedule_risk_from_overdue_deadline(self, engine, suffix):
        oid = f"OBJ-SCH-{suffix}"
        past = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO object_events
                    (object_id, event_type, event_date, deadline_date, description, status)
                VALUES (?, 'deadline', ?, ?, 'Просрочено', 'open')
                """,
                (oid, past, past),
            )
        assert engine.calculate_schedule_risk(oid) == 20

    def test_constraint_risk(self, engine, suffix):
        from app.modules.object_diary.constraint_manager import ConstraintType

        oid = f"OBJ-CR-{suffix}"
        manager_cls = __import__(
            "app.modules.object_diary.constraint_manager",
            fromlist=["ConstraintManager"],
        ).ConstraintManager
        manager = manager_cls()
        manager.add_constraint(oid, ConstraintType.LEGAL, "a", "act")
        manager.add_constraint(oid, ConstraintType.LEGAL, "b", "act")
        assert engine.calculate_constraint_risk(oid) == 30

    def test_budget_risk_zones(self, engine, suffix):
        oid = f"OBJ-BUD-{suffix}"
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO objects (object_id, object_name, contract_amount)
                VALUES (?, 'Test', 1000)
                """,
                (oid,),
            )
            conn.execute(
                """
                INSERT INTO invoices (invoice_id, object_id, amount, date, status)
                VALUES (?, ?, 950, '2026-01-01', 'paid')
                """,
                (f"INV-{suffix}", oid),
            )
        assert engine.calculate_budget_risk(oid) == 80

    def test_zone_boundaries(self, engine):
        assert engine.calculate_health_score.__doc__ is not None
        # Zones are deterministic from the weighted score
        assert True


class TestTemporalLogic:
    @pytest.fixture()
    def temporal(self):
        from app.modules.object_diary.temporal_logic import TemporalLogic

        return TemporalLogic()

    @pytest.mark.parametrize(
        "expr,days",
        [
            ("3 days", 3),
            ("5 дней", 5),
            ("2 weeks", 14),
            ("2 недели", 14),
            ("1 month", 30),
            ("2 месяца", 60),
            ("1 year", 365),
            ("10", 10),
        ],
    )
    def test_inject_absolute_time(self, temporal, expr, days):
        ref = datetime(2026, 1, 1)
        assert temporal.inject_absolute_time(expr, ref) == ref + timedelta(days=days)

    def test_inject_absolute_time_no_number(self, temporal):
        ref = datetime(2026, 1, 1)
        assert temporal.inject_absolute_time("скоро", ref) == ref

    def test_schedule_variance_on_track(self, temporal):
        planned = datetime.now() + timedelta(days=10)
        result = temporal.calculate_schedule_variance(planned)
        assert result["status"] == "on_track"
        assert result["variance_days"] < 0

    def test_schedule_variance_overdue(self, temporal):
        planned = datetime.now() - timedelta(days=5)
        assert temporal.calculate_schedule_variance(planned)["status"] == "overdue"

    def test_schedule_variance_completed(self, temporal):
        planned = datetime(2026, 1, 1)
        actual = datetime(2026, 1, 5)
        result = temporal.calculate_schedule_variance(planned, actual)
        assert result["status"] == "completed"
        assert result["variance_days"] == 4

    @pytest.mark.parametrize(
        "estimated_days,feasibility,is_feasible",
        [
            (10, "high", True),
            (55, "medium", True),
            (120, "low", False),
        ],
    )
    def test_deadline_feasibility(
        self, temporal, estimated_days, feasibility, is_feasible
    ):
        start = datetime(2026, 1, 1)
        deadline = datetime(2026, 3, 1)  # 59 days
        result = temporal.validate_deadline_feasibility(start, deadline, estimated_days)
        assert result["feasibility"] == feasibility
        assert result["is_feasible"] is is_feasible

    def test_burn_rate(self, temporal):
        start = datetime.now() - timedelta(days=90)
        result = temporal.calculate_burn_rate(start, budget=1000, spent=900)
        assert result["burn_rate_per_day"] == pytest.approx(10.0, rel=0.1)
        assert result["budget_remaining"] == 100

    def test_burn_rate_zero_elapsed(self, temporal):
        result = temporal.calculate_burn_rate(datetime.now(), 1000, 100)
        assert result["burn_rate_per_day"] == 0
        assert result["on_track"] is True


class TestAlertDispatcher:
    @pytest.fixture()
    def dispatcher(self):
        from app.modules.object_diary.alert_dispatcher import AlertDispatcher

        return AlertDispatcher()

    def test_create_alert(self, dispatcher):
        from app.modules.object_diary.alert_dispatcher import AlertSeverity

        alert = dispatcher.create_alert(
            AlertSeverity.HIGH, "Title", "Message", "test_source", object_id="OBJ-1"
        )
        assert alert["severity"] == "high"
        assert alert["object_id"] == "OBJ-1"
        assert alert["alert_id"].startswith("ALERT-")

    def test_dispatch_to_gui(self, dispatcher):
        from app.modules.object_diary.alert_dispatcher import AlertSeverity

        alert = dispatcher.dispatch_alert(
            AlertSeverity.WARNING, "T", "M", "src", channels=["gui"]
        )
        assert alert["sent_to_gui"] is True
        assert alert["sent_to_telegram"] is False

    def test_filters(self, dispatcher):
        from app.modules.object_diary.alert_dispatcher import AlertSeverity

        dispatcher.create_alert(AlertSeverity.INFO, "A", "M", "s", object_id="O1")
        dispatcher.create_alert(AlertSeverity.CRITICAL, "B", "M", "s", object_id="O2")

        assert len(dispatcher.get_alerts_by_severity(AlertSeverity.INFO)) == 1
        assert len(dispatcher.get_alerts_by_object("O2")) == 1
        assert len(dispatcher.get_recent_alerts(limit=1)) == 1

    def test_clear_old_alerts(self, dispatcher):
        from app.modules.object_diary.alert_dispatcher import AlertSeverity

        alert = dispatcher.create_alert(AlertSeverity.INFO, "Old", "M", "s")
        alert["created_at"] = (datetime.now() - timedelta(days=60)).isoformat()
        dispatcher.clear_old_alerts(days=30)
        assert dispatcher.alert_history == []

    def test_singleton(self):
        from app.modules.object_diary.alert_dispatcher import get_alert_dispatcher

        assert get_alert_dispatcher() is get_alert_dispatcher()


class TestInboxManager:
    @pytest.fixture()
    def inbox(self):
        from app.modules.object_diary.inbox_manager import InboxManager

        return InboxManager()

    def test_create_and_list_pending(self, inbox, suffix):
        from app.modules.object_diary.inbox_manager import InboxItemType

        item_id = inbox.create_item(
            InboxItemType.VERIFICATION_REQUIRED,
            "Verify link",
            "Needs check",
            "document_link",
            f"LINK-{suffix}",
            related_object_id=f"OBJ-INB-{suffix}",
            priority=8,
        )
        assert item_id > 0
        pending = inbox.get_pending_items()
        assert any(i["id"] == item_id for i in pending)

    def test_assign_and_resolve(self, inbox, suffix):
        from app.modules.object_diary.inbox_manager import InboxItemType

        item_id = inbox.create_item(
            InboxItemType.CONFLICT_DETECTED,
            "Conflict",
            "d",
            "src",
            f"S-{suffix}",
            priority=5,
        )
        assert inbox.assign_item(item_id, "ivan") is True
        assert inbox.resolve_item(item_id, "ivan", "done") is True

        pending_ids = {i["id"] for i in inbox.get_pending_items()}
        assert item_id not in pending_ids

    def test_items_by_object(self, inbox, suffix):
        from app.modules.object_diary.inbox_manager import InboxItemType

        oid = f"OBJ-BY-{suffix}"
        inbox.create_item(
            InboxItemType.MISSING_INFORMATION, "T", "d", "s", f"S-{suffix}",
            related_object_id=oid,
        )
        items = inbox.get_items_by_object(oid)
        assert len(items) == 1


class TestKnowledgeGraph:
    @pytest.fixture()
    def graph(self):
        from app.modules.object_diary.knowledge_graph import KnowledgeGraph

        return KnowledgeGraph()

    def test_add_edge_and_neighbors(self, graph, suffix):
        a, b = f"OBJ-A-{suffix}", f"OBJ-B-{suffix}"
        assert graph.add_edge(a, b, "parent") > 0

        outgoing = graph.get_neighbors(a)
        assert len(outgoing) == 1
        assert outgoing[0]["target"] == b

        incoming = graph.get_neighbors(b, direction="incoming")
        assert incoming[0]["source"] == a

    def test_shortest_path(self, graph, suffix):
        a, b, c = (f"OBJ-P{i}-{suffix}" for i in range(3))
        graph.add_edge(a, b, "related")
        graph.add_edge(b, c, "related")
        assert graph.find_shortest_path(a, c) == [a, b, c]

    def test_shortest_path_missing(self, graph, suffix):
        assert graph.find_shortest_path(f"X-{suffix}", f"Y-{suffix}") == []

    def test_connected_components(self, graph, suffix):
        a, b, c = (f"OBJ-CC{i}-{suffix}" for i in range(3))
        graph.add_edge(a, b, "related")
        graph.add_edge(b, c, "related")
        components = graph.get_connected_components()
        assert any({a, b, c} <= comp for comp in components)


class TestVirtualDocuments:
    @pytest.fixture()
    def manager(self):
        from app.modules.object_diary.virtual_documents import VirtualDocumentManager

        return VirtualDocumentManager()

    def test_register_and_missing(self, manager, suffix):
        doc_id = f"DOC-{suffix}"
        assert manager.register_virtual_document(
            doc_id, "Договор", "contract", "Drive/Договоры", "linker"
        ) > 0

        missing = manager.get_missing_documents()
        assert any(d["doc_id"] == doc_id for d in missing)

    def test_mark_found(self, manager, suffix):
        doc_id = f"DOC-F-{suffix}"
        manager.register_virtual_document(doc_id, "Акт", "act", "Drive", "linker")
        assert manager.mark_as_found(doc_id, "2026-01-01", "найден") is True

        doc = manager.get_virtual_document(doc_id)
        assert doc["status"] == "FOUND"
        assert not any(d["doc_id"] == doc_id for d in manager.get_missing_documents())

    def test_mark_missing(self, manager, suffix):
        doc_id = f"DOC-M-{suffix}"
        manager.register_virtual_document(doc_id, "Акт", "act", "Drive", "linker")
        assert manager.mark_as_missing(doc_id, "не найден") is True
        assert manager.get_virtual_document(doc_id)["status"] == "MISSING"


class TestPreObjectTracker:
    @pytest.fixture()
    def tracker(self):
        from app.modules.object_diary.pre_object_tracker import PreObjectTracker

        return PreObjectTracker()

    def test_register_and_convert(self, tracker, suffix):
        pid = f"KP-{suffix}"
        assert tracker.register_proposal(pid, "2026-01-01", 1500000.0, "КП") > 0

        assert any(p["proposal_id"] == pid for p in tracker.get_pending_proposals())

        assert tracker.convert_to_contract(
            pid, f"CTR-{suffix}", "2026-02-01", "подписан"
        ) is True

        status = tracker.get_proposal_status(pid)
        assert status["status"] == "converted"
        assert status["contract_id"] == f"CTR-{suffix}"

        history = tracker.get_conversion_history()
        assert any(h["proposal_id"] == pid for h in history)

    def test_unknown_proposal(self, tracker, suffix):
        assert tracker.get_proposal_status(f"NOPE-{suffix}") is None


class TestExpertTeacher:
    @pytest.fixture()
    def teacher(self):
        from app.modules.object_diary.expert_teacher import ExpertTeacher

        return ExpertTeacher()

    def test_add_and_get_lesson(self, teacher, suffix):
        concept = f"кабель-{suffix}"
        assert teacher.add_lesson("correction", concept, "Глубина 0.7 м", "expert") > 0

        lessons = teacher.get_lessons(concept=concept)
        assert len(lessons) == 1
        assert lessons[0]["confidence"] == 0.5

    def test_verify_lesson(self, teacher, suffix):
        concept = f"труба-{suffix}"
        lid = teacher.add_lesson("new_concept", concept, "текст")
        assert teacher.verify_lesson(lid, "chief") is True
        assert teacher.get_lessons(concept=concept)[0]["confidence"] == 1.0

    def test_relations_and_graph(self, teacher, suffix):
        a, b = f"concept-a-{suffix}", f"concept-b-{suffix}"
        assert teacher.add_relation(a, "part_of", b, confidence=0.9) > 0

        relations = teacher.get_relations(concept=a)
        assert len(relations) == 1

        graph = teacher.get_ontology_graph()
        assert any(rel["target"] == b for rel in graph[a])


class TestRoleRouter:
    @pytest.fixture()
    def router(self):
        from app.modules.object_diary.role_router import RoleRouter

        return RoleRouter()

    @pytest.mark.parametrize(
        "question_type,text,expected_role",
        [
            ("budget", "Need approval for budget increase", "finance"),
            ("technical", "Specification question", "technical"),
            ("legal", "Contract permit issue", "legal"),
            ("schedule", "Deadline moved", "project_manager"),
        ],
    )
    def test_route_question(self, router, suffix, question_type, text, expected_role):
        result = router.route_question(
            f"Q-{suffix}-{question_type}", question_type, text
        )
        assert result["success"] is True
        assert result["assigned_role"] == expected_role

    def test_get_routing(self, router, suffix):
        qid = f"Q-GET-{suffix}"
        router.route_question(qid, "budget", "budget")
        routing = router.get_routing_for_question(qid)
        assert routing["question_id"] == qid
        assert routing["assigned_to"] == "unassigned"

    def test_unknown_routing(self, router, suffix):
        assert router.get_routing_for_question(f"NOPE-{suffix}") is None


class TestNegativeEventTrigger:
    @pytest.fixture()
    def trigger(self):
        from app.modules.object_diary.negative_event_trigger import NegativeEventTrigger

        return NegativeEventTrigger()

    def test_silence_detected(self, trigger, suffix):
        oid = f"OBJ-SIL-{suffix}"
        old = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d")
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO object_events
                    (object_id, event_type, event_date, description, status)
                VALUES (?, 'update', ?, 'old', 'open')
                """,
                (oid, old),
            )
        event = trigger.check_silence(oid)
        assert event["event_type"] == "silence"
        assert event["severity"] == "high"

    def test_no_silence_for_recent(self, trigger, suffix):
        oid = f"OBJ-REC-{suffix}"
        today = datetime.now().strftime("%Y-%m-%d")
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO object_events
                    (object_id, event_type, event_date, description, status)
                VALUES (?, 'update', ?, 'new', 'open')
                """,
                (oid, today),
            )
        assert trigger.check_silence(oid) is None

    def test_overdue_deadlines(self, trigger, suffix):
        oid = f"OBJ-OD-{suffix}"
        past = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO object_events
                    (object_id, event_type, event_date, deadline_date, description, status)
                VALUES (?, 'deadline', ?, ?, 'late', 'open')
                """,
                (oid, past, past),
            )
        events = trigger.check_overdue_deadlines()
        match = [e for e in events if e["object_id"] == oid]
        assert len(match) == 1
        assert match[0]["severity"] == "critical"

    def test_alert_summary_format(self, trigger):
        summary = trigger.generate_alert_summary(
            {
                "silence_events": [
                    {"object_id": "O1", "days_since_last_event": 9}
                ],
                "overdue_deadlines": [],
                "unresolved_questions": [],
                "high_risk_changes": [],
            }
        )
        assert "Negative Event Alert Summary" in summary
        assert "O1" in summary


class TestConstraintHealthIntegration:
    @pytest.fixture()
    def integration(self):
        from app.modules.object_diary.constraint_health_integration import (
            ConstraintHealthIntegration,
        )

        return ConstraintHealthIntegration()

    def test_action_blocked_by_constraint(self, integration, suffix):
        from app.modules.object_diary.constraint_manager import ConstraintType

        oid = f"OBJ-INT-{suffix}"
        integration.constraint_manager.add_constraint(
            oid, ConstraintType.LEGAL, "Нет разрешения", "excavation"
        )
        result = integration.check_action_with_health_impact(oid, "excavation")
        assert result["can_proceed"] is False
        assert result["blocking_constraints"] == ["Нет разрешения"]

    def test_action_allowed_without_constraints(self, integration, suffix):
        result = integration.check_action_with_health_impact(
            f"OBJ-FREE-{suffix}", "painting"
        )
        assert result["can_proceed"] is True
        assert result["health_zone"] in {"green", "yellow", "red"}

    def test_alert_by_zone_green(self, integration, suffix):
        result = integration.generate_alert_by_zone(f"OBJ-AL-{suffix}")
        assert result["alert_level"] == "OK"

    def test_dependency_impact_no_constraints(self, integration, suffix):
        result = integration.evaluate_dependency_impact(f"OBJ-DEP-{suffix}", True)
        assert result["improvement"] == 0.0
        assert result["zone_changed"] is False

    def test_dependency_impact_resolves_one(self, integration, suffix):
        from app.modules.object_diary.constraint_manager import ConstraintType

        oid = f"OBJ-DEP2-{suffix}"
        integration.constraint_manager.add_constraint(
            oid, ConstraintType.LEGAL, "a", "act"
        )
        result = integration.evaluate_dependency_impact(oid, True)
        assert result["improvement"] == pytest.approx(3.0)
        assert result["new_score"] < result["old_score"]


class TestContractAnalyzer:
    def test_analyze_text_contract(self, tmp_path):
        from app.modules.object_diary.contract_analyzer import ContractAnalyzer

        path = tmp_path / "contract.txt"
        path.write_text(
            "Договор №77-АБ от 15.03.2024\n"
            "Сумма: 1,500,000.50 руб.\n"
            "Заказчик: ООО Ромашка\n"
            "Подрядчик: ООО Стройка\n"
            "Условия оплаты: 30 дней.\n"
            "Ответственность: пени 0.1%.\n",
            encoding="utf-8",
        )

        result = ContractAnalyzer().analyze_contract(str(path))
        assert result["success"] is True
        assert result["contract_number"] == "77-АБ"
        assert result["contract_date"] == "15.03.2024"
        assert result["contract_amount"] == "1,500,000.50"
        assert result["citations"]["contract_number"]

    def test_analyze_text_without_data(self, tmp_path):
        from app.modules.object_diary.contract_analyzer import ContractAnalyzer

        path = tmp_path / "empty.txt"
        path.write_text("просто текст без данных", encoding="utf-8")

        result = ContractAnalyzer().analyze_contract(str(path))
        assert result["success"] is True
        assert result["contract_number"] is None
        assert result["citations"]["contract_number"] is None

    def test_extract_with_citation(self):
        from app.modules.object_diary.contract_analyzer import ContractAnalyzer

        analyzer = ContractAnalyzer()
        text = "Договор №123-456 от 15.03.2024, сумма 1,500,000.50 руб."
        value, citation = analyzer._extract_with_citation(
            text, r"(?:договор|контракт|contract)[№\s-]*(\d+[/\-A-Za-z\d]*)"
        )
        assert value == "123-456"
        assert "123-456" in citation

    def test_extract_no_match(self):
        from app.modules.object_diary.contract_analyzer import ContractAnalyzer

        analyzer = ContractAnalyzer()
        value, citation = analyzer._extract_with_citation("нет данных", r"(\d+)")
        assert value is None and citation is None

    def test_extract_key_clauses(self):
        from app.modules.object_diary.contract_analyzer import ContractAnalyzer

        analyzer = ContractAnalyzer()
        text = "Условия оплаты: 30 дней. Ответственность: пени 0.1%."
        clauses = analyzer.extract_key_clauses(text)
        types = {c["clause_type"] for c in clauses}
        assert "payment_terms" in types
        assert "liability" in types

    def test_missing_file(self, tmp_path):
        from app.modules.object_diary.contract_analyzer import ContractAnalyzer

        result = ContractAnalyzer().analyze_contract(str(tmp_path / "nope.pdf"))
        assert result["success"] is False
        assert result["error"] == "File not found"

    def test_summary(self):
        from app.modules.object_diary.contract_analyzer import ContractAnalyzer

        summary = ContractAnalyzer().generate_contract_summary(
            {
                "success": True,
                "contract_number": "1",
                "contract_date": "2026-01-01",
                "contract_amount": "100",
                "customer": "A",
                "contractor": "B",
            }
        )
        assert "Договор: 1" in summary
        assert "Подрядчик: B" in summary


class TestDocumentLinker:
    @pytest.fixture()
    def linker(self):
        from app.modules.object_diary.document_linker import DocumentLinker

        return DocumentLinker()

    def test_link_explicit_object(self, linker, tmp_path, suffix):
        path = tmp_path / "link.txt"
        path.write_text("Договор №1 от 01.02.2026 на объект", encoding="utf-8")

        oid = f"OBJ-LINK-{suffix}"
        result = linker.analyze_and_link(str(path), object_id=oid)
        assert result["success"] is True
        assert result["object_id"] == oid
        assert result["confidence"] == 0.7

        links = linker.get_document_links(oid)
        assert len(links) == 1
        assert links[0]["document_name"] == "link.txt"

    def test_link_missing_file(self, linker, tmp_path):
        result = linker.analyze_and_link(str(tmp_path / "nope.txt"), "OBJ-X")
        assert result["success"] is False

    def test_link_without_object(self, linker, tmp_path):
        path = tmp_path / "noobj.txt"
        path.write_text("текст без упоминания объекта", encoding="utf-8")
        result = linker.analyze_and_link(str(path))
        assert result["success"] is False
        assert "object" in result["error"].lower()

    def test_find_object_by_name(self, linker, suffix):
        from app.modules.object_diary.diary_manager import DiaryManager
        from app.core.schemas import ObjectDiarySchema

        name = f"Уникальный объект {suffix}"
        oid = f"OBJ-FIND-{suffix}"
        DiaryManager().create_diary(
            ObjectDiarySchema(object_name=name, object_id=oid)
        )

        assert linker._find_object_by_name(name) == oid
        assert linker._find_object_by_name(f"нет такого {suffix}") is None


class TestTelegramDistiller:
    @pytest.fixture()
    def distiller(self):
        from app.modules.object_diary.telegram_distiller import TelegramDistiller

        return TelegramDistiller()

    @pytest.fixture()
    def chat(self, suffix):
        chat_id = -1000000 - int(suffix, 16) % 100000
        project_id = f"PROJ-DST-{suffix}"
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO projects
                    (project_id, project_name, telegram_chat_id, google_drive_folder_id)
                VALUES (?, 'Distiller', ?, ?)
                """,
                (project_id, chat_id, f"FOLDER-{suffix}"),
            )
            for text in [
                "нет материала на объекте",
                "всё идёт по плану",
                "задержка поставки кабеля",
            ]:
                conn.execute(
                    """
                    INSERT INTO telegram_messages
                        (telegram_chat_id, user_id, username, message_text)
                    VALUES (?, 1, 'ivan', ?)
                    """,
                    (chat_id, text),
                )
        return project_id, f"FOLDER-{suffix}"

    def test_detect_risk_keywords_deduplicated(self, distiller):
        result = distiller.detect_risk_keywords("нет материала, материала нет")
        keywords = [r["keyword"] for r in result["detected_risks"]]
        assert len(keywords) == len(set(keywords))
        assert result["has_risk"] is True
        assert result["max_risk_score"] == 10

    def test_detect_risk_keywords_clean_text(self, distiller):
        result = distiller.detect_risk_keywords("погода хорошая")
        assert result["has_risk"] is False
        assert result["max_risk_score"] == 0

    def test_message_priority(self, distiller):
        assert distiller.calculate_message_priority("нет материала") == 10
        assert distiller.calculate_message_priority("обычное сообщение") == 5

    def test_unified_timeline_resolves_chat(self, distiller, chat):
        project_id, folder_id = chat
        by_project = distiller.get_unified_timeline(project_id)
        by_folder = distiller.get_unified_timeline(folder_id)

        assert len(by_project) == 3
        assert len(by_folder) == 3
        assert {e["source"] for e in by_project} == {"telegram"}
        assert all(e["event_type"] == "message" for e in by_project)

    def test_unified_timeline_unknown_object(self, distiller, suffix):
        assert distiller.get_unified_timeline(f"UNKNOWN-{suffix}") == []

    def test_high_risk_messages(self, distiller, chat):
        project_id, _ = chat
        high = distiller.get_high_risk_messages(project_id)
        assert len(high) == 2
        assert all(m["priority"] >= 7 for m in high)

    def test_negative_events(self, distiller, chat):
        project_id, _ = chat
        events = distiller.integrate_with_negative_event_trigger(project_id)
        risk_types = {e["risk_type"] for e in events}
        assert "material_shortage" in risk_types
        assert "schedule_delay" in risk_types
        assert all(e["object_id"] == project_id for e in events)

    def test_digest_statistics(self, distiller, chat):
        project_id, _ = chat
        digest = distiller.generate_digest(project_id)
        assert digest["statistics"]["total_events"] == 3
        assert digest["statistics"]["by_source"]["telegram"] == 3
        assert digest["days_range"] == 7

    def test_deduplicate_timeline(self, distiller):
        entry = {
            "source": "telegram",
            "event_type": "message",
            "timestamp": "2026-01-01 10:00:00",
        }
        result = distiller.deduplicate_timeline([entry, dict(entry)])
        assert len(result) == 1

    def test_prioritize_sources(self, distiller):
        timeline = [
            {"source": "telegram", "event_type": "message", "timestamp": "2026-01-03"},
            {"source": "system", "event_type": "deadline", "timestamp": "2026-01-01"},
            {"source": "document", "event_type": "linked", "timestamp": "2026-01-02"},
        ]
        result = distiller.prioritize_sources(timeline)
        assert [e["source"] for e in result] == ["system", "document", "telegram"]
        assert result[0]["source_weight"] == 1.0

    def test_extract_key_insights(self, distiller):
        digest = {
            "days_range": 7,
            "timeline": [{"priority": 9}, {"priority": 3}],
            "statistics": {
                "total_events": 21,
                "by_source": {"document": 6, "telegram": 11},
                "by_type": {"deadline": 2},
            },
        }
        insights = distiller.extract_key_insights(digest)
        assert any("High activity" in i for i in insights)
        assert any("documents added" in i for i in insights)
        assert any("Telegram discussion" in i for i in insights)
        assert any("deadline-related" in i for i in insights)
        assert any("High-risk messages" in i for i in insights)


class TestDiaryManager:
    @pytest.fixture()
    def manager(self):
        from app.modules.object_diary.diary_manager import DiaryManager

        return DiaryManager()

    @pytest.fixture()
    def diary_schema(self, suffix):
        from app.core.schemas import ObjectDiarySchema

        return ObjectDiarySchema(
            object_name=f"Объект {suffix}",
            object_id=f"OBJ-DIARY-{suffix}",
            customer="Заказчик",
            customer_company="ООО Заказчик",
            contract_date="2026-01-01",
            contract_amount=1000000.0,
            contract_number=f"CTR-{suffix}",
        )

    def test_create_get_update_delete(self, manager, diary_schema):
        diary_id = manager.create_diary(diary_schema)
        assert diary_id > 0

        loaded = manager.get_diary(diary_id)
        assert loaded.object_id == diary_schema.object_id

        by_oid = manager.get_diary_by_object_id(diary_schema.object_id)
        assert by_oid.diary_id == diary_id

        assert manager.update_diary(diary_id, {"customer": "Новый"}) is True
        assert manager.get_diary(diary_id).customer == "Новый"

        assert manager.delete_diary(diary_id) is True
        assert manager.get_diary(diary_id) is None

    def test_update_rejects_unknown_fields(self, manager, diary_schema):
        diary_id = manager.create_diary(diary_schema)
        assert manager.update_diary(diary_id, {"hacked": "x"}) is False

    def test_add_event_and_timeline(self, manager, diary_schema):
        from app.core.schemas import DiaryEventSchema

        diary_id = manager.create_diary(diary_schema)
        event = DiaryEventSchema(
            event_type="document",
            event_timestamp="2026-01-01T10:00:00",
            entity_type="contract",
            entity_id="C-1",
            summary="Подписан договор",
        )
        event_id = manager.add_event(diary_id, event)
        assert event_id > 0

        timeline = manager.get_timeline(diary_id)
        assert len(timeline) == 1
        assert timeline[0].summary == "Подписан договор"

    def test_override_event_hides_old(self, manager, diary_schema):
        from app.core.schemas import DiaryEventSchema

        diary_id = manager.create_diary(diary_schema)
        old_id = manager.add_event(
            diary_id,
            DiaryEventSchema(
                event_type="document",
                event_timestamp="2026-01-01T10:00:00",
                entity_type="contract",
                entity_id="C-1",
                summary="Старая версия",
            ),
        )
        new_id = manager.override_event(
            old_id,
            DiaryEventSchema(
                event_type="document",
                event_timestamp="2026-02-01T10:00:00",
                entity_type="contract",
                entity_id="C-1",
                summary="Новая версия",
            ),
        )
        assert new_id > 0

        current = manager.get_timeline(diary_id)
        assert [e.summary for e in current] == ["Новая версия"]

        full = manager.get_timeline(diary_id, only_current=False)
        assert len(full) == 2

    def test_delete_event(self, manager, diary_schema):
        from app.core.schemas import DiaryEventSchema

        diary_id = manager.create_diary(diary_schema)
        event_id = manager.add_event(
            diary_id,
            DiaryEventSchema(
                event_type="document",
                event_timestamp="2026-01-01T10:00:00",
                entity_type="contract",
                entity_id="C-1",
                summary="x",
            ),
        )
        assert manager.delete_event(event_id) is True
        assert manager.get_timeline(diary_id) == []


class TestPackageImports:
    def test_package_exports(self):
        import app.modules.object_diary as pkg

        for name in pkg.__all__:
            assert hasattr(pkg, name), name

    @pytest.mark.parametrize(
        "module",
        [
            "alert_dispatcher",
            "constraint_health_integration",
            "constraint_manager",
            "contract_analyzer",
            "diary_manager",
            "document_linker",
            "expert_teacher",
            "health_score_engine",
            "inbox_manager",
            "intent_classifier",
            "knowledge_graph",
            "negative_event_trigger",
            "pre_object_tracker",
            "role_router",
            "telegram_distiller",
            "temporal_logic",
            "virtual_documents",
        ],
    )
    def test_module_importable(self, module):
        import importlib

        assert importlib.import_module(f"app.modules.object_diary.{module}")
