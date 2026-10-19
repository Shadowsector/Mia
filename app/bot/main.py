"""Точка входа Telegram-бота Mia PM OS.

Запуск:
    python -m app.bot.main

Токен берётся из `.env` (``BOT_TOKEN``). LLM — llama.cpp (``LLAMA_BASE_URL``).
Бот связывает чат с доменными модулями PM OS через ``PmOsAssistant``.
"""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.bot.assistant import PmOsAssistant
from app.modules.delegation.delegation_engine import DelegationEngine
from app.modules.llm.llama_cpp_client import LlamaCppClient
from app.modules.object_diary.health_score_engine import HealthScoreEngine
from app.modules.storage.database import initialize_database
from app.modules.storage.seed_roles import seed_roles_from_employees
from app.modules.telegram import TelegramSender
from app.modules.temporal.alert_dispatcher import AlertDispatcher
from app.modules.temporal.temporal_logic import TemporalLogicManager
from config import settings

logger = logging.getLogger(__name__)


def _parse_owner_id(raw: str):
    raw = (raw or "").strip()
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def build_sender() -> TelegramSender:
    """Создать TelegramSender с соблюдением режима «пишу только владельцу».

    При ``TELEGRAM_ALLOWLIST_ONLY=true`` исходящие сообщения разрешены только
    для ``TELEGRAM_OWNER_CHAT_ID``. Если владелец не задан — allowlist пуст и
    бот не отправит НИЧЕГО (безопасный дефолт). Узнать свой chat_id: `/here`.
    """
    if not settings.TELEGRAM_ALLOWLIST_ONLY:
        return TelegramSender()

    owner = _parse_owner_id(settings.TELEGRAM_OWNER_CHAT_ID)
    allowed = {owner} if owner is not None else set()
    if owner is None:
        logger.warning(
            "TELEGRAM_ALLOWLIST_ONLY=true, но TELEGRAM_OWNER_CHAT_ID не задан — "
            "бот не будет отправлять исходящие сообщения. Пришлите боту /here, "
            "чтобы узнать свой chat_id, и впишите его в .env."
        )
    return TelegramSender(allowed_chat_ids=allowed)


def build_alert_dispatcher(sender: TelegramSender, enabled: bool = None, chat_id: str = None):
    """Создать AlertDispatcher, если алерты включены и задан получатель."""
    if enabled is None:
        enabled = settings.ALERTS_ENABLED
    if chat_id is None:
        chat_id = settings.ALERTS_CHAT_ID
    if not enabled:
        return None
    if not chat_id:
        logger.warning(
            "ALERTS_ENABLED=true, но ALERTS_CHAT_ID не задан — фоновые алерты "
            "не запускаются."
        )
        return None
    return AlertDispatcher(
        telegram_sender=sender,
        health_engine=HealthScoreEngine(),
        temporal_manager=TemporalLogicManager(timezone=settings.TIMEZONE),
        admin_user_id=chat_id,
    )


async def _on_startup(application: Application) -> None:
    dispatcher = application.bot_data.get("dispatcher")
    if dispatcher is not None:
        dispatcher.start()
        logger.info("Фоновые алерты PM OS запущены.")


async def _on_shutdown(application: Application) -> None:
    dispatcher = application.bot_data.get("dispatcher")
    if dispatcher is not None:
        dispatcher.stop()
        logger.info("Фоновые алерты PM OS остановлены.")



async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я Миа — ассистент PM OS. Пиши вопрос, я помогу "
        "(а если попросишь «спроси у ...», передам вопрос человеку)."
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Что я умею:\n"
        "• отвечать на вопросы по проектам и документам;\n"
        "• делегировать: «спроси у Светы, когда будет смета по объекту X»;\n"
        "• принимать ответы на делегированные вопросы.\n"
        "Команды: /start, /help, /status, /here."
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    llm: LlamaCppClient = context.application.bot_data["llm"]
    sender: TelegramSender = context.application.bot_data["sender"]
    ok = await asyncio.to_thread(llm.is_available)
    mode = (
        f"только владелец ({settings.TELEGRAM_OWNER_CHAT_ID or 'не задан'})"
        if sender.allowlist_enabled
        else "без ограничений"
    )
    await update.message.reply_text(
        f"llama.cpp: {'доступен' if ok else 'недоступен'} ({settings.LLAMA_BASE_URL})\n"
        f"Исходящие: {mode}"
    )


async def cmd_here(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    await update.message.reply_text(
        "Твой chat_id: {chat_id}\nuser_id: {user_id}\n\n"
        "Впиши chat_id в `.env`:\n"
        "TELEGRAM_OWNER_CHAT_ID={chat_id}\n"
        "ALERTS_CHAT_ID={chat_id}".format(
            chat_id=chat.id if chat else "?",
            user_id=user.id if user else "?",
        )
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if message is None or chat is None or not message.text:
        return

    sender: TelegramSender = context.application.bot_data["sender"]
    sender.register(chat.id)

    assistant: PmOsAssistant = context.application.bot_data["assistant"]
    reply = await asyncio.to_thread(
        assistant.handle_text,
        message.text,
        chat.id,
        user.id if user else None,
        (user.username if user and user.username else ""),
        (chat.title or ""),
    )
    await message.reply_text(reply)


def build_application() -> Application:
    if not settings.BOT_TOKEN:
        raise ValueError(
            "BOT_TOKEN не задан. Заполните BOT_TOKEN в .env (см. .env.example)."
        )

    initialize_database()
    try:
        seed_roles_from_employees(settings.EMPLOYEES_FILE)
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("Не удалось заполнить system_roles: %s", e)

    llm = LlamaCppClient()
    sender = build_sender()
    delegation = DelegationEngine(llm_client=llm, telegram_sender=sender)
    assistant = PmOsAssistant(llm=llm, delegation=delegation)
    dispatcher = build_alert_dispatcher(sender)

    application = (
        Application.builder()
        .token(settings.BOT_TOKEN)
        .post_init(_on_startup)
        .post_shutdown(_on_shutdown)
        .build()
    )
    application.bot_data["llm"] = llm
    application.bot_data["sender"] = sender
    application.bot_data["delegation"] = delegation
    application.bot_data["assistant"] = assistant
    application.bot_data["dispatcher"] = dispatcher

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("here", cmd_here))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )
    return application


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    llm = LlamaCppClient()
    if not llm.is_available():
        logger.warning(
            "llama.cpp недоступен по адресу %s. Поднимите llama-server "
            "(start_llama_server.bat).",
            settings.LLAMA_BASE_URL,
        )
    logger.info("Запуск Mia PM OS bot. LLM: %s", settings.LLAMA_BASE_URL)
    application = build_application()
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
