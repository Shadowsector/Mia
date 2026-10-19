"""Tests for DelegationEngine (RFC v1.9) and AccuracyContourManager."""

from datetime import datetime, timedelta

import pytest

from app.modules.storage.database import initialize_database, get_db_connection


@pytest.fixture(scope="module", autouse=True)
def db():
    initialize_database()
    yield


@pytest.fixture()
def suffix():
    import uuid

    return uuid.uuid4().hex[:8]


@pytest.fixture()
def engine():
    from app.modules.delegation.delegation_engine import DelegationEngine

    return DelegationEngine()


@pytest.fixture()
def roles(suffix):
    """Two role rows sharing a name prefix, cleaned up afterwards."""
    prefix = f"U-TEST-{suffix}"
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO system_roles (user_id, username, role, object_id) VALUES (?,?,?,?)",
            (f"{prefix}-1", f"Света{suffix}", "PURCHASING", f"OBJ-{suffix}"),
        )
        cur.execute(
            "INSERT INTO system_roles (user_id, username, role, object_id) VALUES (?,?,?,?)",
            (f"{prefix}-2", f"Светлана{suffix}", "LEGAL", f"OBJ-{suffix}"),
        )
    yield prefix
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM system_roles WHERE user_id LIKE ?", (f"{prefix}%",))
        cur.execute(
            "DELETE FROM delegated_questions WHERE assigned_user_id LIKE ?",
            (f"{prefix}%",),
        )


class TestDelegationEngine:
    def test_parse_delegation_request(self, engine):
        request = engine.parse_delegation_request("Спроси у Светы про сроки", "OBJ-1")
        assert request.target_name == "Света"
        assert request.question_context == "Спроси у Светы про сроки"
        assert request.object_id == "OBJ-1"
        assert request.status == "PENDING"
        assert request.request_id is None

    def test_find_user_by_name(self, engine, roles, suffix):
        found = engine.find_user_by_name(suffix, f"OBJ-{suffix}")
        assert len(found) == 2
        assert {row["user_id"] for row in found} == {f"{roles}-1", f"{roles}-2"}

    def test_find_user_by_name_no_match(self, engine, suffix):
        assert engine.find_user_by_name(f"Нет-{suffix}", f"OBJ-{suffix}") == []

    def test_resolve_ambiguous_user(self, engine):
        assert engine.resolve_ambiguous_user([], "") is None
        assert engine.resolve_ambiguous_user([{"user_id": "u1"}], "") == {"user_id": "u1"}
        assert engine.resolve_ambiguous_user([{"a": 1}, {"b": 2}], "") is None

    def test_choose_channel_defaults_to_public(self, engine):
        assert engine._choose_communication_channel({"user_id": "u1"}) == "PUBLIC"

    def test_delegate_and_intercept_answer(self, engine, suffix):
        request = engine.parse_delegation_request("Вопрос", f"OBJ-{suffix}")
        user = {
            "user_id": f"U-TEST-{suffix}-1",
            "username": f"Света{suffix}",
            "role": "PURCHASING",
        }

        question_id = engine.delegate_question(request, user)
        assert question_id > 0

        pending = engine.get_pending_questions(user["user_id"])
        assert [q["question_id"] for q in pending] == [question_id]
        assert pending[0]["message_sent"] == 1
        assert pending[0]["communication_channel"] == "PUBLIC"

        deadline = datetime.fromisoformat(pending[0]["deadline_for_reply"])
        assert timedelta(hours=3) < deadline - datetime.now() <= timedelta(hours=4)

        assert engine.intercept_answer("Да, сроки согласованы", question_id) is True
        assert engine.get_pending_questions(user["user_id"]) == []

    def test_intercept_answer_unknown_question(self, engine):
        assert engine.intercept_answer("text", 10**9) is False

    def test_get_pending_questions_without_filter(self, engine, suffix):
        request = engine.parse_delegation_request("Вопрос", f"OBJ-{suffix}")
        user = {
            "user_id": f"U-TEST-{suffix}-1",
            "username": f"Света{suffix}",
            "role": "PURCHASING",
        }
        question_id = engine.delegate_question(request, user)
        assert question_id in [q["question_id"] for q in engine.get_pending_questions()]

    def test_check_escalation_reminds_then_escalates(self, engine, suffix):
        user_id = f"U-TEST-{suffix}-1"
        now = datetime.now()

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO delegated_questions
                   (original_request_id, assigned_user_id, assigned_user_role,
                    communication_channel, deadline_for_reply)
                   VALUES (1, ?, 'PURCHASING', 'PUBLIC', ?)""",
                (user_id, (now - timedelta(hours=5)).isoformat()),
            )
            reminded_id = cur.lastrowid
            cur.execute(
                """INSERT INTO delegated_questions
                   (original_request_id, assigned_user_id, assigned_user_role,
                    communication_channel, deadline_for_reply)
                   VALUES (1, ?, 'PURCHASING', 'PUBLIC', ?)""",
                (user_id, (now - timedelta(hours=30)).isoformat()),
            )
            escalated_id = cur.lastrowid

        escalated = engine.check_escalation()
        assert escalated_id in [q["question_id"] for q in escalated]
        assert reminded_id not in [q["question_id"] for q in escalated]

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT question_id, reminder_count, escalation_status, escalated_to_user_id "
                "FROM delegated_questions WHERE question_id IN (?, ?)",
                (reminded_id, escalated_id),
            )
            rows = {r["question_id"]: dict(r) for r in cur.fetchall()}

        assert rows[reminded_id]["escalation_status"] == "REMINDED"
        assert rows[reminded_id]["reminder_count"] == 1
        assert rows[escalated_id]["escalation_status"] == "ESCALATED"
        assert rows[escalated_id]["escalated_to_user_id"] == "admin"

    def test_check_escalation_is_idempotent_for_reminders(self, engine, suffix):
        user_id = f"U-TEST-{suffix}-1"
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO delegated_questions
                   (original_request_id, assigned_user_id, assigned_user_role,
                    communication_channel, deadline_for_reply, escalation_status)
                   VALUES (1, ?, 'PURCHASING', 'PUBLIC', ?, 'REMINDED')""",
                (user_id, (datetime.now() - timedelta(hours=5)).isoformat()),
            )
            qid = cur.lastrowid

        engine.check_escalation()
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT reminder_count, escalation_status FROM delegated_questions WHERE question_id = ?",
                (qid,),
            )
            row = cur.fetchone()
        assert row["reminder_count"] == 0
        assert row["escalation_status"] == "REMINDED"


class TestAccuracyContourMethod1:
    @pytest.fixture()
    def manager(self):
        from app.modules.accuracy.accuracy_contour import AccuracyContourManager

        return AccuracyContourManager()

    def test_regulatory_rules_loaded(self, manager):
        assert "earthworks" in manager.regulatory_rules
        assert "OATI_NOTIFICATION" in manager.regulatory_rules["earthworks"]

    def test_all_constraints_present_is_ok(self, manager):
        from app.modules.accuracy.accuracy_contour import CheckStatus

        state = {"OATI_NOTIFICATION": True, "STAMP_OPS_MGGT": True}
        result = manager.method1_networkx_check("earthworks", state)
        assert result.status == CheckStatus.OK
        assert result.violations == []
        assert result.bypass_strict_rule is False

    def test_missing_constraints_block(self, manager):
        from app.modules.accuracy.accuracy_contour import CheckStatus

        result = manager.method1_networkx_check("earthworks", {"OATI_NOTIFICATION": True})
        assert result.status == CheckStatus.BLOCK
        assert result.blocking_constraints == ["STAMP_OPS_MGGT"]
        assert "Missing constraint: STAMP_OPS_MGGT" in result.violations

    def test_bypass_turns_block_into_warning(self, manager):
        from app.modules.accuracy.accuracy_contour import CheckStatus

        result = manager.method1_networkx_check(
            "earthworks",
            {},
            bypass_strict_rule=True,
            bypass_reason="Разрешение получено по телефону",
        )
        assert result.status == CheckStatus.WARNING
        assert result.bypass_strict_rule is True
        assert result.bypass_reason == "Разрешение получено по телефону"
        assert len(result.violations) == 2

    def test_bypass_without_reason_still_blocks(self, manager):
        from app.modules.accuracy.accuracy_contour import CheckStatus

        result = manager.method1_networkx_check(
            "earthworks", {}, bypass_strict_rule=True, bypass_reason=None
        )
        assert result.status == CheckStatus.BLOCK

    def test_unknown_action_is_ok(self, manager):
        from app.modules.accuracy.accuracy_contour import CheckStatus

        assert manager.method1_networkx_check("painting", {}).status == CheckStatus.OK


class TestAccuracyContourGraph:
    @pytest.fixture()
    def manager(self):
        from app.modules.accuracy.accuracy_contour import AccuracyContourManager

        return AccuracyContourManager()

    def test_acyclic_graph(self, manager):
        manager.build_dependency_graph(
            [
                {"constraint_id": "A"},
                {"constraint_id": "B", "depends_on": ["A"]},
                {"constraint_id": "C", "depends_on": ["B"]},
            ]
        )
        stats = manager.check_constraint_network("OBJ-1")
        assert stats["has_cycles"] is False
        assert stats["num_components"] == 1
        assert stats["largest_component_size"] == 3

    def test_cycle_detected(self, manager):
        manager.build_dependency_graph(
            [
                {"constraint_id": "A", "depends_on": ["B"]},
                {"constraint_id": "B", "depends_on": ["A"]},
            ]
        )
        assert manager.check_constraint_network("OBJ-1")["has_cycles"] is True

    def test_empty_graph(self, manager):
        manager.build_dependency_graph([])
        stats = manager.check_constraint_network("OBJ-1")
        assert stats == {
            "has_cycles": False,
            "num_components": 0,
            "largest_component_size": 0,
        }


class TestAccuracyContourMethods:
    @pytest.fixture()
    def manager(self):
        from app.modules.accuracy.accuracy_contour import AccuracyContourManager

        return AccuracyContourManager()

    def test_method2_placeholder_ok(self, manager):
        from app.modules.accuracy.accuracy_contour import CheckStatus

        result = manager.method2_rag_check("спецификация", ["ref"], rag_manager=object())
        assert result.status == CheckStatus.OK
        assert result.anomalies == []
        assert result.confidence == 0.8

    def test_method3_placeholder_ok(self, manager):
        from app.modules.accuracy.accuracy_contour import CheckStatus

        result = manager.method3_telegram_check([{"text": "начнём завтра"}], [])
        assert result.status == CheckStatus.OK
        assert result.informal_deadlines == []

    def test_consensus_block_wins(self, manager):
        from app.modules.accuracy.accuracy_contour import (
            CheckStatus,
            Method1Result,
            Method2Result,
            Method3Result,
        )

        m1 = Method1Result()
        m1.status = CheckStatus.BLOCK
        m1.violations = ["Missing constraint: STAMP_OPS_MGGT"]
        m2 = Method2Result()
        m2.status = CheckStatus.OK
        m3 = Method3Result()
        m3.status = CheckStatus.OK

        result = manager.consensus_arbiter(m1, m2, m3)
        assert result.final_status == CheckStatus.BLOCK
        assert result.resolution == "Formal blocking constraints take precedence"
        assert result.conflicts == m1.violations
        assert result.method_outputs["method1"]["status"] == "BLOCK"

    def test_consensus_bypass_warning(self, manager):
        from app.modules.accuracy.accuracy_contour import (
            CheckStatus,
            Method1Result,
            Method2Result,
            Method3Result,
        )

        m1 = Method1Result()
        m1.status = CheckStatus.BLOCK
        m1.violations = ["Missing constraint: STAMP_OPS_MGGT"]
        m2 = Method2Result()
        m3 = Method3Result()
        m3.bypass_strict_rule = True
        m3.bypass_reason = "Работы согласованы в чате"

        result = manager.consensus_arbiter(m1, m2, m3)
        assert result.final_status == CheckStatus.WARNING
        assert "Работы согласованы в чате" in result.resolution
        assert result.conflicts == ["Formal vs Informal deadline conflict"]

    def test_consensus_all_ok(self, manager):
        from app.modules.accuracy.accuracy_contour import (
            CheckStatus,
            Method1Result,
            Method2Result,
            Method3Result,
        )

        m1, m2, m3 = Method1Result(), Method2Result(), Method3Result()
        for method in (m1, m2, m3):
            method.status = CheckStatus.OK

        result = manager.consensus_arbiter(m1, m2, m3)
        assert result.final_status == CheckStatus.OK
        assert result.resolution == "All methods agree: OK"

    def test_consensus_anomalies_warning(self, manager):
        from app.modules.accuracy.accuracy_contour import (
            CheckStatus,
            Method1Result,
            Method2Result,
            Method3Result,
        )

        m1 = Method1Result()
        m1.status = CheckStatus.OK
        m2 = Method2Result()
        m2.status = CheckStatus.WARNING
        m2.anomalies = [{"description": "Сумма в акте выше сметы"}]
        m3 = Method3Result()
        m3.status = CheckStatus.OK

        result = manager.consensus_arbiter(m1, m2, m3)
        assert result.final_status == CheckStatus.WARNING
        assert result.conflicts == ["Сумма в акте выше сметы"]

    def test_consensus_unknown(self, manager):
        from app.modules.accuracy.accuracy_contour import (
            CheckStatus,
            Method1Result,
            Method2Result,
            Method3Result,
        )

        m1 = Method1Result()
        m1.status = CheckStatus.UNKNOWN
        result = manager.consensus_arbiter(m1, Method2Result(), Method3Result())
        assert result.final_status == CheckStatus.UNKNOWN
        assert result.resolution == "Unable to determine consensus"

    def test_run_full_audit_without_optional_inputs(self, manager):
        from app.modules.accuracy.accuracy_contour import CheckStatus

        result = manager.run_full_audit(
            "earthworks", {"OATI_NOTIFICATION": True, "STAMP_OPS_MGGT": True}
        )
        # Methods 2 and 3 stay UNKNOWN when their inputs are missing.
        assert result.final_status == CheckStatus.UNKNOWN
        assert result.method_outputs["method1"]["status"] == "OK"

    def test_run_full_audit_blocks(self, manager):
        from app.modules.accuracy.accuracy_contour import CheckStatus

        result = manager.run_full_audit("earthworks", {})
        assert result.final_status == CheckStatus.BLOCK
        assert result.method_outputs["method2"]["status"] == "UNKNOWN"

    def test_run_full_audit_with_spec_and_messages(self, manager):
        from app.modules.accuracy.accuracy_contour import CheckStatus

        result = manager.run_full_audit(
            "earthworks",
            {"OATI_NOTIFICATION": True, "STAMP_OPS_MGGT": True},
            specification_text="Спецификация",
            telegram_messages=[{"text": "копаем завтра"}],
            rag_manager=object(),
        )
        assert result.final_status == CheckStatus.OK
        assert result.method_outputs["method2"]["confidence"] == 0.8
