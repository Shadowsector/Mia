"""Alert Dispatcher - Reminder and Critical Alert Management - RFC v1.9"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, time
from enum import Enum
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncio

from app.modules.storage.database import get_db_connection

logger = logging.getLogger(__name__)


class AlertType(str, Enum):
    """Тип алерта"""
    REMINDER = "REMINDER"
    CRITICAL = "CRITICAL"
    DAILY_DIGEST = "DAILY_DIGEST"


class AlertStatus(str, Enum):
    """Статус алерта"""
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


class AlertSchema:
    """Схема алерта"""

    def __init__(
        self,
        alert_type: AlertType = AlertType.REMINDER,
        recipient_id: str = "",
        message: str = "",
        scheduled_at: Optional[datetime] = None,
    ):
        self.alert_id: Optional[str] = None
        self.alert_type = alert_type
        self.recipient_id = recipient_id
        self.message = message
        self.scheduled_at = scheduled_at or datetime.now()
        self.sent_at: Optional[datetime] = None
        self.status: AlertStatus = AlertStatus.PENDING
        self.channel: str = "telegram"  # telegram, email, etc.


class AlertDispatcher:
    """
    Диспетчер алертов для проактивных уведомлений в рабочее время
    APScheduler для регулярных напоминаний (10:00) и критических тревог (16:00)
    """

    def __init__(self, telegram_sender=None, health_engine=None, temporal_manager=None,
                 admin_user_id: str = "admin"):
        """
        Args:
            telegram_sender: объект с методом `send(recipient_id, message)`.
                При отсутствии алерты только логируются (fallback).
            health_engine: `HealthScoreEngine` для критических алертов и дайджеста.
            temporal_manager: `TemporalLogicManager` для cron-задач.
            admin_user_id: получатель дайджеста/критических алертов.
        """
        self.scheduler = AsyncIOScheduler()
        self.working_hours_start = time(9, 0)  # 09:00
        self.working_hours_end = time(18, 0)  # 18:00

        self.telegram_sender = telegram_sender
        self.health_engine = health_engine
        self.temporal_manager = temporal_manager
        self.admin_user_id = admin_user_id

        # Инициализация планировщика
        self._initialize_scheduler()

    def set_telegram_sender(self, telegram_sender):
        """Назначить транспорт для отправки алертов."""
        self.telegram_sender = telegram_sender
    
    def _initialize_scheduler(self):
        """Инициализация APScheduler с задачами"""
        # Ежедневный дайджест в 10:00
        self.scheduler.add_job(
            self._send_daily_digest,
            CronTrigger(hour=10, minute=0),
            id='daily_digest',
            name='Daily Digest'
        )
        
        # Проверка критических алертов в 16:00
        self.scheduler.add_job(
            self._check_critical_alerts,
            CronTrigger(hour=16, minute=0),
            id='critical_alerts',
            name='Critical Alerts Check'
        )
        
        # Проверка cron задач каждую минуту
        self.scheduler.add_job(
            self._check_cron_tasks,
            CronTrigger(minute='*'),
            id='cron_tasks',
            name='Cron Tasks Check'
        )
    
    def start(self):
        """Запустить планировщик"""
        if not self.scheduler.running:
            self.scheduler.start()
    
    def stop(self):
        """Остановить планировщик"""
        if self.scheduler.running:
            self.scheduler.shutdown()
    
    def schedule_reminder(
        self,
        recipient_id: str,
        message: str,
        scheduled_at: datetime
    ) -> str:
        """
        Запланировать напоминание
        """
        alert = AlertSchema()
        alert.alert_type = AlertType.REMINDER
        alert.recipient_id = recipient_id
        alert.message = message
        alert.scheduled_at = scheduled_at
        
        # Сохранение в БД
        alert_id = self._save_alert(alert)
        alert.alert_id = f"ALERT_{alert_id}"
        
        # Добавление в планировщик
        self.scheduler.add_job(
            self._send_alert,
            'date',
            run_date=scheduled_at,
            args=[alert],
            id=alert.alert_id
        )
        
        return alert.alert_id
    
    def send_critical_alert(
        self,
        recipient_id: str,
        message: str
    ) -> str:
        """
        Отправить критический алерт немедленно
        """
        alert = AlertSchema()
        alert.alert_type = AlertType.CRITICAL
        alert.recipient_id = recipient_id
        alert.message = message
        alert.scheduled_at = datetime.now()
        
        alert_id = self._save_alert(alert)
        alert.alert_id = f"ALERT_{alert_id}"

        # Немедленная отправка
        try:
            asyncio.create_task(self._send_alert(alert))
        except RuntimeError:
            asyncio.get_event_loop().run_until_complete(self._send_alert(alert))

        return alert.alert_id
    
    def _send_daily_digest(self):
        """Отправить ежедневный дайджест в 10:00"""
        try:
            lines = [f"Дайджест на {datetime.now().strftime('%Y-%m-%d')}"]

            if self.health_engine is not None:
                try:
                    scores = self.health_engine.calculate_all_scores()
                except Exception as e:  # pragma: no cover - defensive
                    logger.warning(f"Health scores unavailable for digest: {e}")
                    scores = {}
                if scores:
                    red = sum(1 for s in scores.values() if s.get("zone") == "red")
                    yellow = sum(1 for s in scores.values() if s.get("zone") == "yellow")
                    lines.append(
                        f"Объектов: {len(scores)}; красная зона: {red}; жёлтая зона: {yellow}"
                    )

            pending = self.get_pending_alerts(self.admin_user_id)
            if pending:
                lines.append(f"Ожидающих уведомлений: {len(pending)}")

            self._dispatch_alert(AlertType.DAILY_DIGEST, self.admin_user_id, "\n".join(lines))
        except Exception as e:  # pragma: no cover - defensive
            logger.error(f"Failed to build daily digest: {e}")

    def _check_critical_alerts(self):
        """Проверить критические алерты в 16:00 (RED зона Health Score)"""
        if self.health_engine is None:
            logger.info("Health engine not configured; skipping critical check")
            return

        try:
            critical = self.health_engine.get_critical_objects()
        except Exception as e:  # pragma: no cover - defensive
            logger.error(f"Critical objects check failed: {e}")
            return

        for obj in critical or []:
            message = (
                f"КРИТИЧНО: объект {obj.get('object_id')} в красной зоне "
                f"(score {obj.get('overall_score')})."
            )
            self._dispatch_alert(AlertType.CRITICAL, self.admin_user_id, message)

    def _check_cron_tasks(self):
        """Проверить cron задачи и разослать алерты"""
        if self.temporal_manager is None:
            return

        try:
            executed = self.temporal_manager.execute_cron_tasks()
        except Exception as e:  # pragma: no cover - defensive
            logger.error(f"Cron tasks execution failed: {e}")
            return

        for task in executed or []:
            text = str(task.get("task_text", ""))
            if "alert" in text.lower() or "критич" in text.lower():
                self._dispatch_alert(AlertType.CRITICAL, self.admin_user_id, text)

    def _dispatch_alert(self, alert_type: AlertType, recipient_id: str, message: str):
        """Сохранить и немедленно отправить алерт (sync-обёртка)."""
        alert = AlertSchema(
            alert_type=alert_type,
            recipient_id=recipient_id,
            message=message,
            scheduled_at=datetime.now(),
        )
        alert_id = self._save_alert(alert)
        alert.alert_id = f"ALERT_{alert_id}"

        try:
            asyncio.create_task(self._send_alert(alert))
        except RuntimeError:
            # Нет запущенного event loop — отправляем синхронно
            asyncio.get_event_loop().run_until_complete(self._send_alert(alert))

    async def _send_alert(self, alert: AlertSchema):
        """Отправить алерт через канал"""
        try:
            # Проверка рабочего времени
            if not self._is_working_hours(alert.scheduled_at.time()):
                # Если не рабочее время, отложить
                logger.info(f"Alert {alert.alert_id} deferred (outside working hours)")
                return

            sent = False
            if self.telegram_sender is not None:
                try:
                    sent = bool(self.telegram_sender.send(alert.recipient_id, alert.message))
                except Exception as e:  # pragma: no cover - defensive
                    logger.warning(f"Telegram alert send failed: {e}")
                    sent = False
            else:
                print(f"Sending alert to {alert.recipient_id}: {alert.message}")
                sent = True

            self._update_alert_status(
                alert.alert_id, AlertStatus.SENT if sent else AlertStatus.FAILED
            )

        except Exception as e:
            logger.error(f"Failed to send alert {alert.alert_id}: {e}")
            self._update_alert_status(alert.alert_id, AlertStatus.FAILED)
    
    def _is_working_hours(self, check_time: time) -> bool:
        """Проверка рабочего времени"""
        return self.working_hours_start <= check_time <= self.working_hours_end
    
    def _save_alert(self, alert: AlertSchema) -> int:
        """Сохранить алерт в БД"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO alert_queue (
                    alert_type, recipient_id, message, scheduled_at, status, channel
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                alert.alert_type.value,
                alert.recipient_id,
                alert.message,
                alert.scheduled_at.isoformat(),
                alert.status.value,
                alert.channel
            ))
            return cursor.lastrowid
    
    def _update_alert_status(self, alert_id: str, status: AlertStatus):
        """Обновить статус алерта"""
        # Извлечение числового ID из alert_id
        numeric_id = alert_id.replace("ALERT_", "")
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE alert_queue 
                SET status = ?, sent_at = ?
                WHERE alert_id = ?
            """, (status.value, datetime.now().isoformat(), numeric_id))
    
    def get_pending_alerts(self, recipient_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Получить pending алерты"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if recipient_id:
                cursor.execute("""
                    SELECT * FROM alert_queue 
                    WHERE status = 'PENDING' AND recipient_id = ?
                    ORDER BY scheduled_at ASC
                """, (recipient_id,))
            else:
                cursor.execute("""
                    SELECT * FROM alert_queue 
                    WHERE status = 'PENDING'
                    ORDER BY scheduled_at ASC
                """)
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def aggregate_notifications(self, recipient_id: str) -> str:
        """
        Агрегировать уведомления для избежания спама
        Объединяет несколько мелких алертов в один
        """
        pending_alerts = self.get_pending_alerts(recipient_id)
        
        if not pending_alerts:
            return ""
        
        if len(pending_alerts) == 1:
            return pending_alerts[0]['message']
        
        # Агрегация сообщений
        aggregated = f"У вас {len(pending_alerts)} уведомления:\n"
        for i, alert in enumerate(pending_alerts, 1):
            aggregated += f"{i}. {alert['message']}\n"
        
        return aggregated
