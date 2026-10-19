"""Integration: TemporalLogic + AlertDispatcher - RFC v1.9"""

from typing import Dict, Any, List
from datetime import datetime

from app.modules.temporal.temporal_logic import TemporalLogicManager
from app.modules.temporal.alert_dispatcher import AlertDispatcher


class TemporalAlertIntegration:
    """
    Интеграция TemporalLogicManager и AlertDispatcher
    Связывание cron задач с алертами
    Генерация сводок за день
    Генерация критических отчетов
    """
    
    def __init__(self):
        self.temporal_manager = TemporalLogicManager()
        self.alert_dispatcher = AlertDispatcher()
    
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
            if 'alert' in task['task_text'].lower():
                # Если задача требует алерта
                alert_id = self.alert_dispatcher.schedule_reminder(
                    recipient_id="admin",  # TODO: Получить реального получателя
                    message=task['task_text'],
                    scheduled_at=datetime.now()
                )
                alerts_generated.append(alert_id)
        
        return {
            'executed_tasks': executed_tasks,
            'alerts_generated': alerts_generated
        }
    
    def generate_daily_summary(self) -> Dict[str, Any]:
        """
        Генерировать сводку за день
        Объединяет все события за день в один алерт
        """
        # TODO: Интеграция с DiaryManager для получения событий за день
        # TODO: Интеграция с HealthScoreEngine для получения общего статуса
        
        summary = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'total_events': 0,
            'health_status': 'GREEN',
            'critical_issues': [],
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
            recipient_id="admin",
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
        # TODO: Интеграция с HealthScoreEngine
        # TODO: Проверка блокирующих ограничений
        
        report = {
            'generated_at': datetime.now(),
            'critical_objects': [],
            'blocking_constraints': [],
            'missing_events': [],
            'action_required': False
        }
        
        if report['critical_objects']:
            report['action_required'] = True
            
            message = "CRITICAL REPORT:\n\n"
            message += f"Critical Objects: {len(report['critical_objects'])}\n"
            
            for obj in report['critical_objects']:
                message += f"- {obj}\n"
            
            # Немедленная отправка критического алерта
            self.alert_dispatcher.send_critical_alert(
                recipient_id="admin",
                message=message
            )
        
        return report
    
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
