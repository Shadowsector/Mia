"""Точка входа Telegram-бота Mia."""

from __future__ import annotations

import logging
import os

from telegram.error import Conflict
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import settings
from mia.assistant.service import AssistantService
from mia.bot.handlers import commands, documents, messages
from mia.core import instance
from mia.core.llm import llm_client
from mia.core.logging_setup import setup_logging
from mia.memory.database import Database
from mia.memory.memory_service import MemoryService
from mia.memory.vector_store import VectorStore

logger = logging.getLogger(__name__)


async def _error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Аккуратно логирует ошибки. При повторных конфликтах (несколько копий
    бота) гасит этот экземпляр, чтобы остался только один."""
    err = context.error
    if isinstance(err, Conflict):
        count = context.application.bot_data.get("_conflict_count", 0) + 1
        context.application.bot_data["_conflict_count"] = count
        logger.warning(
            "Похоже, запущено несколько копий бота (Conflict #%s). "
            "Должен работать только один экземпляр.",
            count,
        )
        if count >= 5:
            logger.critical(
                "Слишком много конфликтов — завершаю этот (лишний) экземпляр бота."
            )
            context.application.stop_running()
        return
    logger.error("Ошибка при обработке обновления: %s", err, exc_info=err)


def build_application() -> Application:
    if not settings.BOT_TOKEN:
        raise ValueError(
            "BOT_TOKEN не задан. Скопируйте .env.example в .env и заполните BOT_TOKEN."
        )

    settings.ensure_dirs()

    # Общие сервисы (единые на всё приложение)
    db = Database()
    vector = VectorStore()
    memory = MemoryService(db=db, vector_store=vector)
    assistant = AssistantService(memory=memory)

    application = Application.builder().token(settings.BOT_TOKEN).build()
    application.bot_data["db"] = db
    application.bot_data["memory"] = memory
    application.bot_data["assistant"] = assistant

    # Команды
    application.add_handler(CommandHandler("start", commands.cmd_start))
    application.add_handler(CommandHandler("help", commands.cmd_help))
    application.add_handler(CommandHandler("stats", commands.cmd_stats))

    # Документы и голосовые
    application.add_handler(MessageHandler(filters.Document.ALL, documents.handle_document))
    application.add_handler(MessageHandler(filters.VOICE, documents.handle_voice))

    # Текст (не команды)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, messages.handle_text)
    )

    application.add_error_handler(_error_handler)

    return application


def main() -> None:
    setup_logging()
    logger.info("Запуск Mia Assistant v%s", __import__("mia").__version__)

    # Защита от двойного запуска (иначе Telegram выдаст конфликт).
    if instance.is_running():
        logger.error(
            "Похоже, бот уже запущен (PID %s). Второй экземпляр не запускаю. "
            "Остановите первый через конфигуратор.",
            instance.get_pid(),
        )
        return

    if not llm_client.is_available():
        logger.warning(
            "Ollama недоступен по адресу %s. Бот запустится, но ответы/эмбеддинги "
            "работать не будут, пока не поднимете Ollama.",
            settings.OLLAMA_BASE_URL,
        )

    application = build_application()
    instance.mark_running(os.getpid())
    instance.start_heartbeat_thread()
    logger.info("Бот запущен. Модель: %s, эмбеддинги: %s",
                settings.LLM_MODEL, settings.EMBED_MODEL)
    try:
        application.run_polling(allowed_updates=["message"])
    finally:
        instance.clear()
        logger.info("Бот остановлен.")


if __name__ == "__main__":
    main()
