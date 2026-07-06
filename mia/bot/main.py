"""Точка входа Telegram-бота Mia."""

from __future__ import annotations

import logging

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import settings
from mia.assistant.service import AssistantService
from mia.bot.handlers import commands, documents, messages
from mia.core.llm import llm_client
from mia.core.logging_setup import setup_logging
from mia.memory.database import Database
from mia.memory.memory_service import MemoryService
from mia.memory.vector_store import VectorStore

logger = logging.getLogger(__name__)


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

    return application


def main() -> None:
    setup_logging()
    logger.info("Запуск Mia Assistant v%s", __import__("mia").__version__)

    if not llm_client.is_available():
        logger.warning(
            "Ollama недоступен по адресу %s. Бот запустится, но ответы/эмбеддинги "
            "работать не будут, пока не поднимете Ollama.",
            settings.OLLAMA_BASE_URL,
        )

    application = build_application()
    logger.info("Бот запущен. Модель: %s, эмбеддинги: %s",
                settings.LLM_MODEL, settings.EMBED_MODEL)
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
