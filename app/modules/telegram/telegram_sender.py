"""TelegramSender - адаптер для доменных модулей Mia PM OS.

Доменные модули (например, ``DelegationEngine`` или ``AlertDispatcher``)
ожидают объект с интерфейсом:

    send(recipient_id, message) -> bool
    can_send_private(user_id)   -> bool

Этот класс инкапсулирует ``python-telegram-bot`` (``telegram.Bot``) и умеет
работать с реальным ботом или с внедрённым объектом (для тестов и
реплеев). Токен берётся из ``settings.BOT_TOKEN`` (переменная окружения
``BOT_TOKEN``).
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Optional, Set

logger = logging.getLogger(__name__)


class TelegramSenderError(Exception):
    """Ошибка инициализации/работы Telegram-отправителя."""


class TelegramSender:
    """Тонкая обёртка над ``telegram.Bot`` для доменных модулей.

    Безопасность: если задан ``allowed_chat_ids`` (в т.ч. пустое множество),
    включён режим allowlist — сообщения уходят ТОЛЬКО указанным chat_id, все
    остальные блокируются и логируются. Это позволяет держать бота в режиме
    «пишу только владельцу».
    """

    def __init__(
        self,
        token: Optional[str] = None,
        bot: Any = None,
        default_chat_id: Optional[int] = None,
        allowed_chat_ids: Optional[Iterable[int]] = None,
    ) -> None:
        self.default_chat_id = default_chat_id
        self._known_chat_ids: Set[int] = set()
        self._allowed_chat_ids: Optional[Set[int]] = None
        if allowed_chat_ids is not None:
            self._allowed_chat_ids = {int(c) for c in allowed_chat_ids}

        if bot is not None:
            self.bot = bot
            return

        token = token or self._token_from_settings()
        if not token:
            raise TelegramSenderError(
                "Не задан BOT_TOKEN (проверьте .env или передайте token=...)"
            )

        try:
            from telegram import Bot  # type: ignore
        except ImportError as e:  # pragma: no cover - зависит от окружения
            raise TelegramSenderError(
                "Пакет python-telegram-bot не установлен: pip install python-telegram-bot"
            ) from e

        self.bot = Bot(token=token)

    @staticmethod
    def _token_from_settings() -> str:
        from config import settings

        return getattr(settings, "BOT_TOKEN", "") or ""

    # ------------------------------------------------------------------
    # Allowlist и учёт известных чатов
    # ------------------------------------------------------------------
    @property
    def allowlist_enabled(self) -> bool:
        return self._allowed_chat_ids is not None

    def add_allowed(self, chat_id: int) -> None:
        """Разрешить отправку в указанный chat_id (в режиме allowlist)."""
        if self._allowed_chat_ids is None:
            self._allowed_chat_ids = set()
        self._allowed_chat_ids.add(int(chat_id))

    def is_allowed(self, chat_id: Any) -> bool:
        try:
            cid = int(chat_id)
        except (TypeError, ValueError):
            return False
        if self._allowed_chat_ids is None:
            return True
        return cid in self._allowed_chat_ids

    def register(self, chat_id: int) -> None:
        """Запомнить chat_id (вызывается при получении сообщения)."""
        if chat_id is not None:
            self._known_chat_ids.add(int(chat_id))

    def _resolve_chat_id(self, recipient_id: Any) -> Optional[int]:
        if recipient_id is None:
            return self.default_chat_id
        try:
            return int(recipient_id)
        except (TypeError, ValueError):
            logger.warning("Некорректный recipient_id: %r", recipient_id)
            return None

    # ------------------------------------------------------------------
    # Интерфейс для доменных модулей
    # ------------------------------------------------------------------
    def send(self, recipient_id: Any, message: str) -> bool:
        """Отправить сообщение. Возвращает True при успехе.

        В режиме allowlist отправка кому-либо, кроме разрешённых, блокируется.
        """
        chat_id = self._resolve_chat_id(recipient_id)
        if chat_id is None:
            logger.warning("Не удалось определить chat_id для %r", recipient_id)
            return False

        if self._allowed_chat_ids is not None and chat_id not in self._allowed_chat_ids:
            logger.warning(
                "Отправка заблокирована (allowlist): chat_id=%s вне разрешённого "
                "списка %s. Сообщение: %s",
                chat_id,
                sorted(self._allowed_chat_ids),
                message[:120],
            )
            return False

        try:
            self.bot.send_message(chat_id=chat_id, text=message)
            return True
        except Exception as e:  # pragma: no cover - сетевые/Telegram-ошибки
            logger.warning("Telegram send failed (chat_id=%s): %s", chat_id, e)
            return False

    def can_send_private(self, user_id: Any) -> bool:
        """Может ли бот написать пользователю в ЛС.

        В режиме allowlist — только разрешённым chat_id. Иначе — только тем,
        кто уже писал боту в текущей сессии.
        """
        if self._allowed_chat_ids is not None:
            return self.is_allowed(user_id)
        try:
            return int(user_id) in self._known_chat_ids
        except (TypeError, ValueError):
            return False

