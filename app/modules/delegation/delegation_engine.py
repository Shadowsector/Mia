"""Delegation Engine - Dynamic Delegation Pattern (Ask Sveta) - RFC v1.9"""

import asyncio
import concurrent.futures
import logging
import uuid
from typing import Optional, List, Dict, Any, Callable, Awaitable
from datetime import datetime, timedelta

from app.core.schemas import DelegationRequestSchema
from app.modules.storage.database import get_db_connection
from app.modules.llm.ollama_client import PromptTemplates

logger = logging.getLogger(__name__)

DEFERRED_DEADLINE_HOURS = 4
ESCALATION_HOURS = 24


class DelegationEngine:
    """
    Паттерн «Спроси у Светы» (динамическая делегация)
    Граф ролей в SQLite, контекстный парсинг имен, выбор канала связи
    """

    def __init__(
        self,
        llm_client=None,
        telegram_sender=None,
        model: str = "qwen2.5:14b-instruct-q4_K_M",
        admin_user_id: str = "admin",
    ):
        """
        Args:
            llm_client: экземпляр `OllamaClient` (async) для парсинга запросов и ответов.
            telegram_sender: объект с методом `send(recipient_id, message)` и,
                опционально, `can_send_private(user_id)`. Если не задан, сообщения
                логируются в stdout (fallback).
            model: модель Ollama для задач делегации.
            admin_user_id: получатель эскалаций.
        """
        self.llm_client = llm_client
        self.telegram_sender = telegram_sender
        self.model = model
        self.admin_user_id = admin_user_id

    # ==================== LLM helper ====================

    def _run_async(self, factory: Callable[[], Awaitable[Any]]) -> Any:
        """
        Выполнить async-вызов LLM из синхронного кода.
        Если event loop уже запущен (внутри бота), корутина выполняется
        в отдельном потоке с собственным loop.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(factory())

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(lambda: asyncio.run(factory())).result()

    def _ask_llm_json(self, prompt: str) -> Dict[str, Any]:
        """Синхронная обёртка над `OllamaClient.generate_json` c fallback."""
        if self.llm_client is None:
            return {}

        try:
            return self._run_async(
                lambda: self.llm_client.generate_json(prompt, model=self.model)
            )
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"LLM delegation call failed: {e}")
            return {}

    # ==================== Парсинг запроса ====================

    def parse_delegation_request(
        self,
        text: str,
        context: str
    ) -> DelegationRequestSchema:
        """
        Парсинг запроса делегирования
        LLM extracts question, object, topic, required role
        """
        extracted = self._extract_with_llm(text, context)

        target_name = extracted.get("target_name") or "Света"
        question = extracted.get("question") or text
        object_id = extracted.get("object_id") or context
        requester_id = extracted.get("requester_id") or "user"

        request = DelegationRequestSchema(
            request_id=None,
            requester_id=requester_id,
            target_name=target_name,
            question_context=question,
            object_id=object_id,
            created_at=datetime.now(),
            status="PENDING"
        )

        return request

    def _extract_with_llm(self, text: str, context: str) -> Dict[str, Any]:
        """Извлечь поля запроса делегирования через LLM (если клиент доступен)."""
        if self.llm_client is None:
            return {}

        prompt = PromptTemplates.delegation_extraction_prompt(text, context)
        data = self._ask_llm_json(prompt)
        if not isinstance(data, dict) or data.get("error"):
            return {}
        if data.get("is_delegation") is False:
            return {}
        return {
            "target_name": data.get("target_name"),
            "question": data.get("question"),
            "object_id": data.get("object_id"),
            "requester_id": data.get("requester_id"),
        }

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
        Human-in-the-loop: создать задачу в Inbox для выбора правильного пользователя
        """
        if len(candidates) == 0:
            return None
        elif len(candidates) == 1:
            return candidates[0]
        else:
            self._create_disambiguation_task(candidates, context)
            return None

    def _create_disambiguation_task(
        self,
        candidates: List[Dict[str, Any]],
        context: str
    ) -> Optional[str]:
        """
        Создать задачу в Inbox (questions_gateway) для ручного выбора человека
        при неоднозначном совпадении имени.
        """
        try:
            question_id = f"DELEG-{uuid.uuid4().hex[:12]}"

            def label(candidate: Dict[str, Any]) -> str:
                return str(
                    candidate.get("username")
                    or candidate.get("user_id")
                    or candidate.get("role")
                    or candidate
                )

            options = [label(c) for c in candidates[:2]]
            option_a = options[0] if options else "Вариант 1"
            option_b = options[1] if len(options) > 1 else "Вариант 2"
            option_c = options[2] if len(options) > 2 else None

            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO questions_gateway (
                        question_id, question_type, status, priority, project_id,
                        related_schema_type, related_entity_id, question_markdown,
                        option_a, option_b, option_c
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    question_id,
                    "DELEGATION_DISAMBIGUATION",
                    "open",
                    "normal",
                    context or "GENERAL",
                    "system_roles",
                    "",
                    "Кому адресовать вопрос? Найдено несколько совпадений: "
                    + ", ".join(label(c) for c in candidates),
                    option_a,
                    option_b,
                    option_c,
                ))

            logger.info(f"Created delegation disambiguation task {question_id}")
            return question_id
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"Failed to create disambiguation task: {e}")
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
                (datetime.now() + timedelta(hours=DEFERRED_DEADLINE_HOURS)).isoformat()
            ))

            question_id = cursor.lastrowid

            # Реальная отправка (или fallback в лог)
            sent = self._send_to_user(user, request.question_context, channel)

            # Обновление статуса
            cursor.execute("""
                UPDATE delegated_questions 
                SET message_sent = ? 
                WHERE question_id = ?
            """, (1 if sent else 0, question_id))

            return question_id

    def _choose_communication_channel(self, user: Dict[str, Any]) -> str:
        """
        Выбор канала связи
        ЛС если бот подключен, иначе общий чат с тегом @username
        """
        sender = self.telegram_sender
        if sender is not None and hasattr(sender, "can_send_private"):
            try:
                if sender.can_send_private(user.get("user_id")):
                    return "PRIVATE"
            except Exception as e:  # pragma: no cover - defensive
                logger.warning(f"can_send_private failed: {e}")
        return "PUBLIC"

    def _send_to_user(
        self,
        user: Dict[str, Any],
        message: str,
        channel: str
    ) -> bool:
        """
        Отправить сообщение пользователю.
        Если к адресату привязан @username, добавляется упоминание при PUBLIC-канале.
        """
        text = message
        if channel == "PUBLIC" and user.get("username"):
            text = f"@{user['username']} {message}"

        if self.telegram_sender is not None:
            try:
                return bool(self.telegram_sender.send(user.get("user_id"), text))
            except Exception as e:  # pragma: no cover - defensive
                logger.warning(f"Telegram send failed: {e}")
                return False

        print(f"Sending to {user.get('username')} via {channel}: {text}")
        return True

    def intercept_answer(
        self,
        message: str,
        delegated_question_id: int
    ) -> bool:
        """
        Перехват ответа
        Mistral:7b парсит сообщение → ответ на вопрос или мем?
        """
        if not self._is_answer(message):
            return False

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE delegated_questions 
                SET answer_received = 1, answer_text = ?, answer_timestamp = ?
                WHERE question_id = ?
            """, (message, datetime.now().isoformat(), delegated_question_id))

            return cursor.rowcount > 0

    def _is_answer(self, message: str) -> bool:
        """Определить, является ли сообщение ответом (а не трёпом/мемом)."""
        if self.llm_client is None:
            # Без LLM принимаем любое сообщение как ответ (прежнее поведение)
            return True

        prompt = PromptTemplates.delegation_answer_classifier_prompt(message)
        data = self._ask_llm_json(prompt)
        if not isinstance(data, dict) or "is_answer" not in data:
            return True
        return bool(data.get("is_answer"))

    def check_escalation(self) -> List[Dict[str, Any]]:
        """
        Проверить эскалацию зависших вопросов
        После истечения дедлайна (4 часа) статус PENDING → мягкое напоминание
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

                    if timedelta(0) <= time_diff < timedelta(hours=ESCALATION_HOURS):
                        # Мягкое напоминание (только один раз)
                        if question.get('escalation_status') == 'REMINDED':
                            continue
                        if not self._send_reminder(question):
                            continue
                        question['escalation_status'] = 'REMINDED'
                        question['reminder_count'] = question['reminder_count'] + 1

                        cursor.execute("""
                            UPDATE delegated_questions 
                            SET escalation_status = 'REMINDED', reminder_count = reminder_count + 1
                            WHERE question_id = ?
                        """, (question['question_id'],))

                    elif time_diff >= timedelta(hours=ESCALATION_HOURS):
                        # Эскалация пользователю
                        self._escalate_to_user(question)
                        question['escalation_status'] = 'ESCALATED'
                        question['escalated_to_user_id'] = self.admin_user_id
                        question['escalation_timestamp'] = current_time

                        cursor.execute("""
                            UPDATE delegated_questions 
                            SET escalation_status = 'ESCALATED', escalated_to_user_id = ?,
                                escalation_timestamp = ?
                            WHERE question_id = ?
                        """, (self.admin_user_id, current_time.isoformat(),
                              question['question_id']))

                        escalated_questions.append(question)

        return escalated_questions

    def _send_reminder(self, question: Dict[str, Any]) -> bool:
        """Отправить напоминание отправителю вопроса."""
        message = (
            f"Напоминание: вопрос #{question['question_id']} для "
            f"{question['assigned_user_id']} пока без ответа."
        )
        if self.telegram_sender is not None:
            try:
                return bool(self.telegram_sender.send(question['assigned_user_id'], message))
            except Exception as e:  # pragma: no cover - defensive
                logger.warning(f"Telegram reminder failed: {e}")
                return False

        print(f"Sending reminder to user {question['assigned_user_id']}")
        return True

    def _escalate_to_user(self, question: Dict[str, Any]) -> bool:
        """Эскалировать вопрос пользователю."""
        message = (
            f"Делегированный вопрос #{question['question_id']} к "
            f"{question['assigned_user_id']} не отвечен в течение 24 часов. "
            f"Дедлайн истёк."
        )
        if self.telegram_sender is not None:
            try:
                return bool(self.telegram_sender.send(self.admin_user_id, message))
            except Exception as e:  # pragma: no cover - defensive
                logger.warning(f"Telegram escalation failed: {e}")
                return False

        print(f"Escalating: {message}")
        return True

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
