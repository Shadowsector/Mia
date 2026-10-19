"""Delegation Engine - Dynamic Delegation Pattern (Ask Sveta) - RFC v1.9"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from app.core.schemas import DelegationRequestSchema, DelegatedQuestionSchema
from app.modules.storage.database import get_db_connection


class DelegationEngine:
    """
    Паттерн «Спроси у Светы» (динамическая делегация)
    Граф ролей в SQLite, контекстный парсинг имен, выбор канала связи
    """
    
    def __init__(self):
        pass
    
    def parse_delegation_request(
        self,
        text: str,
        context: str
    ) -> DelegationRequestSchema:
        """
        Парсинг запроса делегирования
        LLM extracts question, object, topic, required role
        """
        # TODO: Интеграция с OllamaClient для парсинга
        # Временная заглушка
        
        request = DelegationRequestSchema(
            request_id=None,
            requester_id="user",  # TODO: Получить из контекста
            target_name="Света",  # TODO: Извлечь из текста
            question_context=text,
            object_id=context,
            created_at=datetime.now(),
            status="PENDING"
        )
        
        return request
    
    def find_user_by_name(
        self,
        name: str,
        object_id: str
    ) -> List[Dict[str, Any]]:
        """
        Найти пользователя по имени
        Контекстный парсинг имен (сопоставление с system_roles)
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM system_roles 
                WHERE username LIKE ? OR user_id LIKE ?
            """, (f"%{name}%", f"%{name}%"))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def resolve_ambiguous_user(
        self,
        candidates: List[Dict[str, Any]],
        context: str
    ) -> Optional[Dict[str, Any]]:
        """
        Разрешить неоднозначность при нескольких совпадениях
        Human-in-the-loop: выбрать правильного пользователя
        """
        if len(candidates) == 0:
            return None
        elif len(candidates) == 1:
            return candidates[0]
        else:
            # Если несколько совпадений → вернуть None для Human-in-the-loop
            # TODO: Создать задачу в Inbox для выбора
            return None
    
    def delegate_question(
        self,
        request: DelegationRequestSchema,
        user: Dict[str, Any]
    ) -> int:
        """
        Делегировать вопрос пользователю
        Выбор канала связи (PRIVATE или PUBLIC)
        """
        # Определение канала связи
        channel = self._choose_communication_channel(user)
        
        # Создание делегированного вопроса
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO delegated_questions (
                    original_request_id, assigned_user_id, assigned_user_role,
                    communication_channel, deadline_for_reply
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                request.request_id if request.request_id else 0,
                user['user_id'],
                user['role'],
                channel,
                (datetime.now() + timedelta(hours=4)).isoformat()  # Дедлайн через 4 часа
            ))
            
            question_id = cursor.lastrowid
            
            # TODO: Реальная отправка через Telegram
            self._send_to_user(user, request.question_context, channel)
            
            # Обновление статуса
            cursor.execute("""
                UPDATE delegated_questions 
                SET message_sent = 1 
                WHERE question_id = ?
            """, (question_id,))
            
            return question_id
    
    def _choose_communication_channel(self, user: Dict[str, Any]) -> str:
        """
        Выбор канала связи
        ЛС если бот подключен, иначе общий чат с тегом @username
        """
        # TODO: Проверка подключения бота к пользователю
        # Временная заглушка
        return "PUBLIC"
    
    def _send_to_user(
        self,
        user: Dict[str, Any],
        message: str,
        channel: str
    ):
        """
        Отправить сообщение пользователю
        """
        # TODO: Интеграция с Telegram
        print(f"Sending to {user['username']} via {channel}: {message}")
    
    def intercept_answer(
        self,
        message: str,
        delegated_question_id: int
    ) -> bool:
        """
        Перехват ответа
        Mistral:7b парсит сообщение → ответ на вопрос или мем?
        """
        # TODO: Интеграция с OllamaClient для анализа ответа
        # Временная заглушка
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE delegated_questions 
                SET answer_received = 1, answer_text = ?, answer_timestamp = ?
                WHERE question_id = ?
            """, (message, datetime.now().isoformat(), delegated_question_id))
            
            return cursor.rowcount > 0
    
    def check_escalation(self) -> List[Dict[str, Any]]:
        """
        Проверить эскалацию зависших вопросов
        Если через 4 часа (рабочее время) статус PENDING → мягкое напоминание
        Если ответа нет сутки → эскалация пользователю
        """
        escalated_questions = []
        current_time = datetime.now()
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM delegated_questions 
                WHERE answer_received = 0 AND escalation_status != 'ESCALATED'
            """)
            
            rows = cursor.fetchall()
            
            for row in rows:
                question = dict(row)
                deadline = question['deadline_for_reply']
                
                if deadline:
                    if isinstance(deadline, str):
                        try:
                            deadline = datetime.fromisoformat(deadline)
                        except ValueError:
                            continue
                    
                    time_diff = current_time - deadline
                    
                    if time_diff >= timedelta(0) and time_diff < timedelta(hours=24):
                        # Мягкое напоминание (только один раз)
                        if question.get('escalation_status') == 'REMINDED':
                            continue
                        self._send_reminder(question)
                        question['escalation_status'] = 'REMINDED'
                        question['reminder_count'] = question['reminder_count'] + 1
                        
                        cursor.execute("""
                            UPDATE delegated_questions 
                            SET escalation_status = 'REMINDED', reminder_count = reminder_count + 1
                            WHERE question_id = ?
                        """, (question['question_id'],))
                        
                    elif time_diff >= timedelta(hours=24):
                        # Эскалация пользователю
                        self._escalate_to_user(question)
                        question['escalation_status'] = 'ESCALATED'
                        question['escalated_to_user_id'] = "admin"
                        question['escalation_timestamp'] = current_time
                        
                        cursor.execute("""
                            UPDATE delegated_questions 
                            SET escalation_status = 'ESCALATED', escalated_to_user_id = 'admin',
                                escalation_timestamp = ?
                            WHERE question_id = ?
                        """, (current_time.isoformat(), question['question_id']))
                        
                        escalated_questions.append(question)
        
        return escalated_questions
    
    def _send_reminder(self, question: Dict[str, Any]):
        """Отправить напоминание"""
        # TODO: Интеграция с Telegram
        print(f"Sending reminder to user {question['assigned_user_id']}")
    
    def _escalate_to_user(self, question: Dict[str, Any]):
        """Эскалировать вопрос пользователю"""
        # TODO: Интеграция с Telegram
        message = (
            f"Денис, delegated question #{question['question_id']} to {question['assigned_user_id']} "
            f"not answered within 24 hours. Deadline exceeded."
        )
        print(f"Escalating: {message}")
    
    def get_pending_questions(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Получить pending вопросы"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if user_id:
                cursor.execute("""
                    SELECT * FROM delegated_questions 
                    WHERE assigned_user_id = ? AND answer_received = 0
                    ORDER BY created_at DESC
                """, (user_id,))
            else:
                cursor.execute("""
                    SELECT * FROM delegated_questions 
                    WHERE answer_received = 0
                    ORDER BY created_at DESC
                """)
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
