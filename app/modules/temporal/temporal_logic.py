"""Temporal Logic Manager - Absolute Time Injection and Relative Date Parsing - RFC v1.9"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json

from app.core.schemas import TemporalContextSchema
from app.modules.storage.database import get_db_connection


class TemporalLogicManager:
    """
    Контур темпоральной логики
    Absolute Time Injection: инъекция абсолютного времени в промпт
    Deternministic time parsing: LLM парсит фразу → JSON, бэкенд математически вычисляет абсолютную дату
    """
    
    def __init__(self, timezone: str = "Europe/Moscow"):
        self.timezone = timezone
    
    def get_temporal_context(self) -> TemporalContextSchema:
        """
        Получить темпоральный контекст
        Absolute Time Injection в промпт
        """
        current_time = datetime.now()
        
        # Relative Translation Map
        relative_map = {
            "Сегодня": current_time.strftime("%Y-%m-%d"),
            "Завтра": (current_time + timedelta(days=1)).strftime("%Y-%m-%d"),
            "Вчера": (current_time - timedelta(days=1)).strftime("%Y-%m-%d"),
            "Позавчера": (current_time - timedelta(days=2)).strftime("%Y-%m-%d"),
            "Через неделю": (current_time + timedelta(days=7)).strftime("%Y-%m-%d"),
            "Через 2 недели": (current_time + timedelta(days=14)).strftime("%Y-%m-%d"),
            "Неделю назад": (current_time - timedelta(days=7)).strftime("%Y-%m-%d"),
            "В этом месяце": current_time.strftime("%Y-%m"),
            "В следующем месяце": (current_time + relativedelta(months=1)).strftime("%Y-%m")
        }
        
        return TemporalContextSchema(
            current_absolute_time=current_time,
            current_day_of_week=current_time.strftime("%A"),
            relative_translation_map=relative_map
        )
    
    def resolve_relative_date(
        self,
        relative_phrase: str,
        base_date: Optional[datetime] = None
    ) -> Optional[datetime]:
        """
        Детерминистический time parsing
        LLM парсит фразу → JSON, бэкенд математически вычисляет абсолютную дату
        """
        if base_date is None:
            base_date = datetime.now()
        
        # Словарь относительных выражений
        relative_mappings = {
            "сегодня": timedelta(days=0),
            "завтра": timedelta(days=1),
            "вчера": timedelta(days=-1),
            "позавчера": timedelta(days=-2),
            "через неделю": timedelta(days=7),
            "через 2 недели": timedelta(days=14),
            "через 3 дня": timedelta(days=3),
            "через 5 дней": timedelta(days=5),
            "неделю назад": timedelta(days=-7),
            "2 недели назад": timedelta(days=-14),
            "в следующем месяце": relativedelta(months=1),
            "в следующем году": relativedelta(years=1)
        }
        
        phrase_lower = relative_phrase.lower().strip()
        
        # Поиск в словаре
        for key, delta in relative_mappings.items():
            if key in phrase_lower:
                if isinstance(delta, relativedelta):
                    return base_date + delta
                else:
                    return base_date + delta
        
        # Парсинг числовых выражений (например, "через 3 дня")
        if "через" in phrase_lower and "дня" in phrase_lower:
            try:
                words = phrase_lower.split()
                for i, word in enumerate(words):
                    if word.isdigit():
                        days = int(word)
                        return base_date + timedelta(days=days)
            except:
                pass
        
        # Если не удалось распознать
        return None
    
    def create_cron_task(
        self,
        task_text: str,
        trigger_date: datetime,
        status: str = "PENDING"
    ) -> int:
        """
        Создать cron задачу в SQLite
        Фиксированная дата выполнения
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO cron_tasks (task_text, trigger_date, status)
                VALUES (?, ?, ?)
            """, (task_text, trigger_date, status))
            return cursor.lastrowid
    
    def execute_cron_tasks(self) -> List[Dict[str, Any]]:
        """
        Исполнить cron задачи
        Проверяет задачи с истекшим дедлайном
        """
        current_time = datetime.now()
        executed_tasks = []
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM cron_tasks 
                WHERE status = 'PENDING' AND trigger_date <= ?
            """, (current_time,))
            
            rows = cursor.fetchall()
            
            for row in rows:
                # Выполнение задачи (логика задачи)
                task_result = self._execute_task_logic(row['task_text'])
                
                # Обновление статуса
                cursor.execute("""
                    UPDATE cron_tasks 
                    SET status = 'COMPLETED', executed_at = ?
                    WHERE task_id = ?
                """, (current_time, row['task_id']))
                
                executed_tasks.append({
                    'task_id': row['task_id'],
                    'task_text': row['task_text'],
                    'trigger_date': row['trigger_date'],
                    'result': task_result
                })
        
        return executed_tasks
    
    def _execute_task_logic(self, task_text: str) -> Dict[str, Any]:
        """
        Логика выполнения задачи
        TODO: Интеграция с другими модулями для реального выполнения
        """
        # Временная заглушка
        return {
            'success': True,
            'message': f"Task executed: {task_text}"
        }
    
    def inject_temporal_context_to_prompt(
        self,
        base_prompt: str
    ) -> str:
        """
        Инъекция темпорального контекста в промпт
        Absolute Time Injection
        """
        context = self.get_temporal_context()
        
        temporal_header = f"""
[ SYSTEM CONTEXT ]
Current Absolute Time: {context.current_absolute_time.strftime('%Y-%m-%d %H:%M:%S')}
Current Day of Week: {context.current_day_of_week}
Relative Translation Map:
"""
        
        for key, value in context.relative_translation_map.items():
            temporal_header += f"- \"{key}\" = {value}\n"
        
        temporal_header += "[ END SYSTEM CONTEXT ]\n\n"
        
        return temporal_header + base_prompt
    
    def parse_intent_with_time(
        self,
        intent_json: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Парсинг намерения с разрешением относительного времени
        LLM возвращает JSON с relative_time, Python вычисляет абсолютную дату
        """
        if 'relative_time' not in intent_json:
            return intent_json
        
        relative_time = intent_json['relative_time']
        absolute_date = self.resolve_relative_date(relative_time)
        
        if absolute_date:
            intent_json['absolute_date'] = absolute_date
            intent_json['relative_time_resolved'] = True
        else:
            intent_json['relative_time_resolved'] = False
            intent_json['resolution_error'] = f"Could not resolve: {relative_time}"
        
        return intent_json
    
    def get_pending_cron_tasks(self) -> List[Dict[str, Any]]:
        """Получить все pending cron задачи"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM cron_tasks 
                WHERE status = 'PENDING'
                ORDER BY trigger_date ASC
            """)
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def cancel_cron_task(self, task_id: int) -> bool:
        """Отменить cron задачу"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE cron_tasks 
                SET status = 'CANCELLED' 
                WHERE task_id = ?
            """, (task_id,))
            return cursor.rowcount > 0
