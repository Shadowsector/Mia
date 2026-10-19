"""PmOsAssistant — оркестратор обработки сообщений для Mia PM OS.

Связывает Telegram-сообщения с доменными модулями PM OS:
  1. перехват ответа на ранее делегированный вопрос;
  2. обнаружение нового запроса делегирования («спроси у Светы...»);
  3. обычный диалог через LLM (llama.cpp).

Класс не зависит от ``python-telegram-bot`` — это позволяет тестировать
логику без сети. Тонкая обвязка Telegram живёт в ``app.bot.main``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.modules.llm.llama_cpp_client import LlamaCppClient, LlamaCppError

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Ты — Миа, ассистент руководителя в системе управления проектами (PM OS).\n"
    "Отвечай по-русски, кратко и по делу. Помогай с вопросами по объектам, "
    "срокам, задачам и документам. Если данных недостаточно — честно скажи "
    "об этом, не выдумывай факты и цифры."
)

_EMPTY_REPLY = "Я на связи! Чем помочь?"
_LLM_FALLBACK = (
    "Не получилось связаться с моделью (llama.cpp). Проверь, запущен ли "
    "llama-server, и попробуй ещё раз."
)


class ConversationMemory:
    """Краткосрочная память диалога по чатам (в процессе, без БД).

    Хранит последние реплики ``user``/``assistant`` для каждого чата, чтобы
    модель видела контекст. Ограничена по числу реплик и по суммарной длине,
    чтобы не раздувать контекст llama.cpp.
    """

    def __init__(self, max_turns: int = 8, max_chars: int = 6000) -> None:
        self.max_turns = max_turns
        self.max_chars = max_chars
        self._store: Dict[str, List[Dict[str, str]]] = {}

    def get(self, key: str) -> List[Dict[str, str]]:
        return list(self._store.get(key, []))

    def append(self, key: str, user_text: str, assistant_text: str) -> None:
        turns = self._store.setdefault(key, [])
        turns.append({"role": "user", "content": user_text})
        turns.append({"role": "assistant", "content": assistant_text})
        self._trim(turns)
        self._store[key] = turns

    def clear(self, key: str) -> None:
        self._store.pop(key, None)

    def _trim(self, turns: List[Dict[str, str]]) -> None:
        if len(turns) > self.max_turns * 2:
            del turns[: len(turns) - self.max_turns * 2]
        while len(turns) > 2 and sum(len(m["content"]) for m in turns) > self.max_chars:
            del turns[:2]


class PmOsAssistant:
    def __init__(
        self,
        llm: Optional[LlamaCppClient] = None,
        delegation: Any = None,
        memory: Optional[ConversationMemory] = None,
    ) -> None:
        self.llm = llm or LlamaCppClient()
        self.delegation = delegation
        self.memory = memory or ConversationMemory()

    # ------------------------------------------------------------------
    # Публичная точка входа
    # ------------------------------------------------------------------
    def handle_text(
        self,
        text: str,
        chat_id: Optional[int] = None,
        user_id: Optional[int] = None,
        username: str = "",
        chat_title: str = "",
    ) -> str:
        text = (text or "").strip()
        if not text:
            return _EMPTY_REPLY

        intercepted = self._maybe_intercept_answer(text, user_id)
        if intercepted is not None:
            return intercepted

        delegated = self._maybe_delegate(text, chat_id, user_id)
        if delegated is not None:
            return delegated

        key = (
            str(chat_id)
            if chat_id is not None
            else (str(user_id) if user_id is not None else "__default__")
        )
        return self._chat(
            text, memory_key=key, chat_title=chat_title, username=username
        )

    def clear_history(self, chat_id: Optional[int] = None) -> None:
        """Сбросить память диалога (для всего или одного чата)."""
        if chat_id is None:
            self.memory = ConversationMemory(
                max_turns=self.memory.max_turns, max_chars=self.memory.max_chars
            )
        else:
            self.memory.clear(str(chat_id))

    # ------------------------------------------------------------------
    # Шаги
    # ------------------------------------------------------------------
    def _maybe_intercept_answer(self, text: str, user_id: Optional[int]) -> Optional[str]:
        if self.delegation is None or user_id is None:
            return None
        try:
            pending = self.delegation.get_pending_questions(str(user_id))
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("get_pending_questions failed: %s", e)
            return None
        if not pending:
            return None

        question_id = pending[0]["question_id"]
        try:
            if self.delegation.intercept_answer(text, question_id):
                return "Спасибо, записала ответ и передала его автору вопроса."
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("intercept_answer failed: %s", e)
        return None

    def _maybe_delegate(
        self, text: str, chat_id: Optional[int], user_id: Optional[int]
    ) -> Optional[str]:
        if self.delegation is None:
            return None

        context = str(chat_id) if chat_id is not None else ""
        try:
            request = self.delegation.try_parse_delegation(text, context)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("try_parse_delegation failed: %s", e)
            return None
        if request is None:
            return None

        try:
            candidates = self.delegation.find_user_by_name(
                request.target_name, request.object_id
            )
            user = self.delegation.resolve_ambiguous_user(
                candidates, request.object_id
            )
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("resolve user failed: %s", e)
            return None

        if user is None:
            return (
                f"Не смогла однозначно определить, кому адресовать вопрос про "
                f"«{request.target_name}». Создала задачу в Inbox для уточнения."
            )

        try:
            question_id = self.delegation.delegate_question(request, user)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("delegate_question failed: %s", e)
            return "Не получилось делегировать вопрос, попробуй позже."

        return (
            f"Передала вопрос {request.target_name}: "
            f"«{request.question_context}» (№{question_id})."
        )

    def _chat(
        self,
        text: str,
        memory_key: str = "__default__",
        chat_title: str = "",
        username: str = "",
    ) -> str:
        system = SYSTEM_PROMPT
        if chat_title:
            system += f"\n\nЧат: {chat_title}."
        if username:
            system += f"\nСобеседник: {username}."

        messages: List[Dict[str, str]] = [{"role": "system", "content": system}]
        messages.extend(self.memory.get(memory_key))
        messages.append({"role": "user", "content": text})

        try:
            reply = self._invoke_llm(messages, system, text) or _LLM_FALLBACK
        except LlamaCppError as e:
            logger.error("LLM chat failed: %s", e)
            return _LLM_FALLBACK

        if reply and reply != _LLM_FALLBACK:
            self.memory.append(memory_key, text, reply)
        return reply

    def _invoke_llm(
        self, messages: List[Dict[str, str]], system: str, text: str
    ) -> str:
        chat = getattr(self.llm, "chat", None)
        if callable(chat):
            return chat(messages)
        return self.llm.complete(system, text)
