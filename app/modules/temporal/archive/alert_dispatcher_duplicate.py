"""Alert Dispatcher - Reminder and Critical Alert Management - RFC v1.9"""

from typing import Optional, List, Dict, Any
from datetime import datetime, time
from enum import Enum
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncio

from app.modules.storage.database import get_db_connection


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
    
    def __init__(self):
        self.alert_id: Optional[str] = None
        self.alert_type: AlertType
        self.recipient_id: str
        self.message: str
        self.scheduled_at: datetime
        self.sent_at: Optional[datetime] = None
        self.status: AlertStatus = AlertStatus.PENDING
        self.channel: str = "telegram"  # telegram, email, etc.


class AlertDispatcher:
    """
    Диспетчер алертов для проактивных уведомлений в рабочее время
    APScheduler для регулярных напоминаний (10:00) и критических тревог (16:00)
    """
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.working_hours_start = time(9, 0)  # 09:00
        self.working_hours_end = time(18, 0)  # 18:00
        
        # Инициализация планировщика
        self._initialize_scheduler()
    
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
        asyncio.create_task(self._send_alert(alert))
        
        return alert.alert_id
    
    def _send_daily_digest(self):
        """Отправить ежедневный дайджест в 10:00"""
        # TODO: Интеграция с Telegram для отправки дайджеста
        print("Sending daily digest...")
    
    def _check_critical_alerts(self):
        """Проверить критические алерты в 16:00"""
        # TODO: Проверка Health Score для RED зоны
        print("Checking critical alerts...")
    
    def _check_cron_tasks(self):
        """Проверить cron задачи"""
        # TODO: Интеграция с TemporalLogicManager
        print("Checking cron tasks...")
    
    async def _send_alert(self, alert: AlertSchema):
        """Отправить алерт через канал"""
        try:
            # Проверка рабочего времени
            if not self._is_working_hours(alert.scheduled_at.time()):
                # Если не рабочее время, отложить
                print(f"Alert {alert.alert_id} deferred (outside working hours)")
                return
            
            # TODO: Реальная отправка через Telegram
            print(f"Sending alert to {alert.recipient_id}: {alert.message}")
            
            # Обновление статуса
            self._update_alert_status(alert.alert_id, AlertStatus.SENT)
            
        except Exception as e:
            print(f"Failed to send alert {alert.alert_id}: {e}")
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
                alert.scheduled_at,
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
            """, (status.value, datetime.now(), numeric_id))
    
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
