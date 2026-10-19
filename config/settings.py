"""
Централизованная конфигурация Mia Assistant.

Все настройки читаются из окружения (.env). Значения по умолчанию
подобраны так, чтобы проект запускался «из коробки» на локальной машине
с Ollama.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Корень проекта = папка на уровень выше config/
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def _get(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return value if value is not None else default


# --- Telegram ---
BOT_TOKEN: str = _get("BOT_TOKEN")
BOT_USERNAME: str = _get("BOT_USERNAME", "@mia_assistant_wd_bot")

# --- Ollama / LLM (легаси-бот mia/) ---
OLLAMA_BASE_URL: str = _get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
LLM_MODEL: str = _get("LLM_MODEL", "qwen2.5:14b-instruct")
EMBED_MODEL: str = _get("EMBED_MODEL", "bge-m3")
LLM_TEMPERATURE: float = float(_get("LLM_TEMPERATURE", "0.6"))
LLM_MAX_TOKENS: int = int(_get("LLM_MAX_TOKENS", "1200"))
LLM_TIMEOUT: int = int(_get("LLM_TIMEOUT", "300"))

# --- llama.cpp / LLM (Mia PM OS, основная система) ---
# llama-server поднимается скриптом start_llama_server.bat / GUI (порт 8080).
LLAMA_BASE_URL: str = _get("LLAMA_BASE_URL", "http://localhost:8080").rstrip("/")
# Имя модели для OpenAI-совместимого API (llama-server принимает любое имя —
# реальная модель определяется загруженным .gguf файлом).
LLAMA_MODEL: str = _get("LLAMA_MODEL", "qwen2.5:14b-instruct")
# Модель для эмбеддингов (нужен llama-server с флагом --embeddings). Пусто —
# использовать основную модель.
LLAMA_EMBED_MODEL: str = _get("LLAMA_EMBED_MODEL", "")

# --- Проактивные алерты PM OS ---
# Включить фоновые алерты (дайджест 10:00, критические объекты 16:00, cron).
ALERTS_ENABLED: bool = _get("ALERTS_ENABLED", "true").lower() in ("1", "true", "yes", "on")
# Telegram chat_id получателя алертов (руководитель/владелец). Пусто — алерты
# только логируются, а фоновый диспетчер не запускается.
ALERTS_CHAT_ID: str = _get("ALERTS_CHAT_ID", "")

# --- Vision / OCR ---
# Модель с поддержкой изображений для распознавания сканов (PDF, фото).
VISION_MODEL: str = _get("VISION_MODEL", "qwen2.5vl:7b")
# Максимум страниц скана для OCR (защита от очень тяжёлых файлов).
OCR_MAX_PAGES: int = int(_get("OCR_MAX_PAGES", "15"))
# Разрешение рендера страниц PDF в изображение (DPI).
OCR_DPI: int = int(_get("OCR_DPI", "180"))

# --- Данные ---
_data_dir_raw = _get("DATA_DIR", str(BASE_DIR / "data"))
DATA_DIR: Path = Path(_data_dir_raw)
if not DATA_DIR.is_absolute():
    DATA_DIR = (BASE_DIR / DATA_DIR).resolve()

DB_PATH: Path = DATA_DIR / "mia.db"
CHROMA_DIR: Path = DATA_DIR / "chroma_db"
UPLOADS_DIR: Path = DATA_DIR / "uploads"
LOGS_DIR: Path = DATA_DIR / "logs"

# --- Время ---
TIMEZONE: str = _get("TIMEZONE", "Europe/Moscow")

# --- AnythingLLM (RAG / агенты для свободных вопросов по документам) ---
ANYTHINGLLM_BASE_URL: str = _get("ANYTHINGLLM_BASE_URL", "http://localhost:3001").rstrip("/")
ANYTHINGLLM_API_KEY: str = _get("ANYTHINGLLM_API_KEY", "")
ANYTHINGLLM_WORKSPACE: str = _get("ANYTHINGLLM_WORKSPACE", "mia")

# --- GitHub (автообновление и отправка логов) ---
# Репозиторий в формате "owner/repo".
GITHUB_REPO: str = _get("GITHUB_REPO", "Shadowsector/Mia")
# Ветка, с которой тянуть обновления. Пусто — использовать текущую ветку.
UPDATE_BRANCH: str = _get("UPDATE_BRANCH", "")
# Токен GitHub (нужен только для отправки логов и приватного репозитория).
GITHUB_TOKEN: str = _get("GITHUB_TOKEN", "")
# Периодичность автопроверки обновлений, минут (0 — только вручную).
AUTO_UPDATE_INTERVAL_MIN: int = int(_get("AUTO_UPDATE_INTERVAL_MIN", "0"))

# --- Справочник сотрудников ---
# Редактируемый файл, который может править владелец (Дэн).
EMPLOYEES_FILE: Path = BASE_DIR / "config" / "employees.json"

# --- Авторитетные источники (их слова = истина) ---
# Денис Кулешов (владелец) и Алексей Калачёв (гендир).
AUTHORITATIVE_USER_IDS: set[int] = {103833998, 21942308}


def ensure_dirs() -> None:
    """Создаёт необходимые директории данных, если их ещё нет."""
    for path in (DATA_DIR, CHROMA_DIR, UPLOADS_DIR, LOGS_DIR):
        path.mkdir(parents=True, exist_ok=True)
