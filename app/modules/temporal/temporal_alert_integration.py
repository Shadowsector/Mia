"""Integration: TemporalLogic + AlertDispatcher - RFC v1.9"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.modules.temporal.temporal_logic import TemporalLogicManager
from app.modules.temporal.alert_dispatcher import AlertDispatcher

logger = logging.getLogger(__name__)


class TemporalAlertIntegration:
    """
    Интеграция TemporalLogicManager и AlertDispatcher
    Связывание cron задач с алертами
    Генерация сводок за день
    Генерация критических отчетов
    """

    def __init__(self, telegram_sender=None, health_engine=None, diary_manager=None,
                 admin_user_id: str = "admin"):
        """
        Args:
            telegram_sender: транспорт для отправки алертов (`send(recipient_id, message)`).
            health_engine: `HealthScoreEngine` для сводок и критических отчётов.
            diary_manager: `DiaryManager` для сбора событий за день.
            admin_user_id: получатель сводок/эскалаций.
        """
        self.temporal_manager = TemporalLogicManager()
        self.health_engine = health_engine
        self.diary_manager = diary_manager
        self.admin_user_id = admin_user_id
        self.alert_dispatcher = AlertDispatcher(
            telegram_sender=telegram_sender,
            health_engine=health_engine,
            temporal_manager=self.temporal_manager,
            admin_user_id=admin_user_id,
        )

    def start(self):
        """Запустить интегрированную систему"""
        self.alert_dispatcher.start()

    def stop(self):
        """Остановить интегрированную систему"""
        self.alert_dispatcher.stop()

    def process_cron_tasks_with_alerts(self) -> Dict[str, Any]:
        """
        Обработать cron задачи и сгенерировать алерты
        Проверка NegativeEventTrigger через cron
        """
        # Шаг 1: Выполнить cron задачи
        executed_tasks = self.temporal_manager.execute_cron_tasks()

        # Шаг 2: Проверить результаты и сгенерировать алерты
        alerts_generated = []

        for task in executed_tasks:
            result = task.get('result') or {}
            is_alert = (
                result.get('task_type') == 'alert'
                or 'alert' in task['task_text'].lower()
            )
            if is_alert:
                # Если задача требует алерта
                alert_id = self.alert_dispatcher.schedule_reminder(
                    recipient_id=self.admin_user_id,
                    message=task['task_text'],
                    scheduled_at=datetime.now()
                )
                alerts_generated.append(alert_id)

        return {
            'executed_tasks': executed_tasks,
            'alerts_generated': alerts_generated
        }

    def _collect_today_events(self) -> List[Dict[str, Any]]:
        """Собрать события всех дневников, датированные сегодня."""
        events: List[Dict[str, Any]] = []
        if self.diary_manager is None:
            return events

        today = datetime.now().date()
        try:
            diaries = self.diary_manager.get_all_diaries()
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"Failed to list diaries for summary: {e}")
            return events

        for diary in diaries:
            diary_id = getattr(diary, "diary_id", None)
            if diary_id is None:
                continue
            try:
                timeline = self.diary_manager.get_timeline(diary_id)
            except Exception as e:  # pragma: no cover - defensive
                logger.warning(f"Failed to read timeline {diary_id}: {e}")
                continue
            for event in timeline:
                ts = getattr(event, "event_timestamp", None)
                if isinstance(ts, datetime) and ts.date() == today:
                    events.append({
                        "object_id": getattr(diary, "object_id", None),
                        "event_type": getattr(event, "event_type", None),
                        "summary": getattr(event, "summary", None),
                    })
        return events

    def generate_daily_summary(self) -> Dict[str, Any]:
        """
        Генерировать сводку за день
        Объединяет все события за день в один алерт
        """
        events = self._collect_today_events()

        health_status = 'GREEN'
        if self.health_engine is not None:
            try:
                scores = self.health_engine.calculate_all_scores()
            except Exception as e:  # pragma: no cover - defensive
                logger.warning(f"Health scores unavailable for summary: {e}")
                scores = {}
            if any(s.get("zone") == "red" for s in scores.values()):
                health_status = 'RED'
            elif any(s.get("zone") == "yellow" for s in scores.values()):
                health_status = 'YELLOW'

        critical_issues = [
            e["summary"] for e in events if e.get("event_type") == "critical"
        ]

        summary = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'total_events': len(events),
            'health_status': health_status,
            'critical_issues': critical_issues,
            'warnings': [],
            'recommendations': []
        }

        # Отправка агрегированного алерта
        message = f"Daily Summary for {summary['date']}\n"
        message += f"Health Status: {summary['health_status']}\n"
        message += f"Total Events: {summary['total_events']}\n"

        if summary['critical_issues']:
            message += f"\nCritical Issues ({len(summary['critical_issues'])}):\n"
            for issue in summary['critical_issues']:
                message += f"- {issue}\n"

        alert_id = self.alert_dispatcher.schedule_reminder(
            recipient_id=self.admin_user_id,
            message=message,
            scheduled_at=datetime.now()
        )

        summary['alert_id'] = alert_id

        return summary

    def generate_critical_report(self) -> Dict[str, Any]:
        """
        Генерировать критический отчет
        Проверка RED зоны в Health Score
        """
        critical_objects: List[Dict[str, Any]] = []
        if self.health_engine is not None:
            try:
                critical_objects = self.health_engine.get_critical_objects()
            except Exception as e:  # pragma: no cover - defensive
                logger.warning(f"Critical objects unavailable: {e}")

        blocking_constraints = (
            self._get_blocking_constraints() if self.health_engine is not None else []
        )

        report = {
            'generated_at': datetime.now(),
            'critical_objects': critical_objects,
            'blocking_constraints': blocking_constraints,
            'missing_events': [],
            'action_required': bool(critical_objects or blocking_constraints)
        }

        if report['action_required']:
            message = "CRITICAL REPORT:\n\n"
            message += f"Critical Objects: {len(report['critical_objects'])}\n"

            for obj in report['critical_objects']:
                label = obj.get('object_id') if isinstance(obj, dict) else str(obj)
                message += f"- {label}\n"

            if blocking_constraints:
                message += f"\nBlocking Constraints: {len(blocking_constraints)}\n"
                for constraint in blocking_constraints:
                    message += f"- {constraint}\n"

            # Немедленная отправка критического алерта
            self.alert_dispatcher.send_critical_alert(
                recipient_id=self.admin_user_id,
                message=message
            )

        return report

    @staticmethod
    def _get_blocking_constraints() -> List[str]:
        """Получить невыполненные (блокирующие) ограничения из БД."""
        try:
            from app.modules.storage.database import get_db_connection

            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT constraint_name FROM constraints
                    WHERE status = 'NOT_SATISFIED'
                """)
                return [row['constraint_name'] for row in cursor.fetchall()]
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"Failed to read blocking constraints: {e}")
            return []
    
    def schedule_relative_reminder(
        self,
        recipient_id: str,
        message: str,
        relative_time: str
    ) -> str:
        """
        Запланировать напоминание с относительным временем
        LLM extracts relative_time → Python resolves absolute date
        """
        # Разрешение относительного времени
        absolute_date = self.temporal_manager.resolve_relative_date(relative_time)
        
        if absolute_date:
            # Установка времени на 09:00 (начало рабочего дня)
            absolute_date = absolute_date.replace(hour=9, minute=0, second=0)
            
            alert_id = self.alert_dispatcher.schedule_reminder(
                recipient_id=recipient_id,
                message=message,
                scheduled_at=absolute_date
            )
            
            return alert_id
        else:
            raise ValueError(f"Could not resolve relative time: {relative_time}")
    
    def process_delegated_question_timeout(
        self,
        question_id: int,
        assigned_user_id: str,
        deadline: datetime
    ) -> str:
        """
        Обработать тайм-аут делегированного вопроса
        Эскалация пользователю через 24 часа
        """
        if datetime.now() >= deadline:
            # Эскалация
            message = (
                f"Денис, delegated question #{question_id} to {assigned_user_id} "
                f"not answered within 24 hours. Timeout exceeded."
            )
            
            alert_id = self.alert_dispatcher.send_critical_alert(
                recipient_id="admin",
                message=message
            )
            
            return alert_id
        
        return None
