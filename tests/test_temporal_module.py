"""Tests for the temporal module (RFC v1.9)."""

from datetime import datetime, timedelta

import pytest

from app.modules.storage.database import initialize_database, get_db_connection


@pytest.fixture(scope="module", autouse=True)
def db():
    initialize_database()
    yield


class TestTemporalPackage:
    def test_package_exports(self):
        import app.modules.temporal as pkg

        assert set(pkg.__all__) == {
            "TemporalLogicManager",
            "AlertDispatcher",
            "TemporalAlertIntegration",
        }
        for name in pkg.__all__:
            assert hasattr(pkg, name), name

    def test_gui_import_target_exists(self):
        from app.modules.temporal.temporal_logic import TemporalLogicManager

        assert callable(TemporalLogicManager)


class TestTemporalLogicManager:
    @pytest.fixture()
    def manager(self):
        from app.modules.temporal.temporal_logic import TemporalLogicManager

        return TemporalLogicManager()

    def test_temporal_context(self, manager):
        context = manager.get_temporal_context()
        assert context.current_absolute_time.date() == datetime.now().date()
        assert context.current_day_of_week
        assert "Сегодня" in context.relative_translation_map

    @pytest.mark.parametrize(
        "phrase,delta",
        [
            ("сегодня", timedelta(days=0)),
            ("завтра", timedelta(days=1)),
            ("вчера", timedelta(days=-1)),
            ("через неделю", timedelta(days=7)),
            ("через 2 недели", timedelta(days=14)),
            ("неделю назад", timedelta(days=-7)),
        ],
    )
    def test_resolve_relative_date(self, manager, phrase, delta):
        base = datetime(2026, 1, 10, 12, 0, 0)
        assert manager.resolve_relative_date(phrase, base) == base + delta

    def test_resolve_unknown_phrase(self, manager):
        assert manager.resolve_relative_date("когда-нибудь", datetime(2026, 1, 1)) is None

    def test_inject_context_into_prompt(self, manager):
        prompt = manager.inject_temporal_context_to_prompt("Привет")
        assert prompt.startswith("\n[ SYSTEM CONTEXT ]")
        assert "Привет" in prompt
        assert prompt.rstrip().endswith("Привет")

    def test_parse_intent_with_time(self, manager):
        result = manager.parse_intent_with_time({"relative_time": "завтра"})
        assert result["relative_time_resolved"] is True
        assert isinstance(result["absolute_date"], datetime)

    def test_parse_intent_without_time(self, manager):
        intent = {"action": "query"}
        assert manager.parse_intent_with_time(intent) == intent

    def test_parse_intent_unresolved(self, manager):
        result = manager.parse_intent_with_time({"relative_time": "непонятно"})
        assert result["relative_time_resolved"] is False
        assert "resolution_error" in result


class TestCronTasks:
    @pytest.fixture()
    def manager(self):
        from app.modules.temporal.temporal_logic import TemporalLogicManager

        return TemporalLogicManager()

    def test_create_and_cancel(self, manager):
        task_id = manager.create_cron_task(
            "напомнить про акт", datetime.now() + timedelta(days=1)
        )
        assert task_id > 0

        pending_ids = {t["task_id"] for t in manager.get_pending_cron_tasks()}
        assert task_id in pending_ids

        assert manager.cancel_cron_task(task_id) is True
        pending_ids = {t["task_id"] for t in manager.get_pending_cron_tasks()}
        assert task_id not in pending_ids

    def test_execute_due_tasks(self, manager):
        task_id = manager.create_cron_task("срочный alert", datetime.now() - timedelta(hours=1))
        executed = manager.execute_cron_tasks()
        assert any(t["task_id"] == task_id for t in executed)

        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT status FROM cron_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
        assert row["status"] == "COMPLETED"

        assert manager.execute_cron_tasks() == [] or all(
            t["task_id"] != task_id for t in manager.execute_cron_tasks()
        )


class TestTemporalAlertIntegration:
    @pytest.fixture()
    def integration(self):
        from app.modules.temporal.temporal_alert_integration import (
            TemporalAlertIntegration,
        )

        return TemporalAlertIntegration()

    def test_components_initialized(self, integration):
        from app.modules.temporal.alert_dispatcher import AlertDispatcher
        from app.modules.temporal.temporal_logic import TemporalLogicManager

        assert isinstance(integration.temporal_manager, TemporalLogicManager)
        assert isinstance(integration.alert_dispatcher, AlertDispatcher)

    def test_schedule_relative_reminder(self, integration):
        alert_id = integration.schedule_relative_reminder(
            "admin", "проверить объект", "через 2 недели"
        )
        assert alert_id.startswith("ALERT_")

    def test_schedule_relative_reminder_invalid(self, integration):
        with pytest.raises(ValueError):
            integration.schedule_relative_reminder("admin", "x", "непонятно")

    def test_process_cron_tasks_with_alerts(self, integration):
        integration.temporal_manager.create_cron_task(
            "alert: проверить сроки", datetime.now() - timedelta(minutes=5)
        )
        result = integration.process_cron_tasks_with_alerts()
        assert "executed_tasks" in result
        assert "alerts_generated" in result

    def test_daily_summary(self, integration):
        summary = integration.generate_daily_summary()
        assert summary["date"] == datetime.now().strftime("%Y-%m-%d")
        assert summary["alert_id"].startswith("ALERT_")

    def test_critical_report(self, integration):
        report = integration.generate_critical_report()
        assert report["action_required"] is False

    def test_delegated_question_timeout_not_due(self, integration):
        assert (
            integration.process_delegated_question_timeout(
                1, "user", datetime.now() + timedelta(hours=1)
            )
            is None
        )
