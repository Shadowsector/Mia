"""Постоянное хранилище (SQLite): полный лог сообщений и напоминания.

Это ядро памяти «помнить всё и всегда»: КАЖДОЕ сообщение из чатов
сохраняется здесь, независимо от того, ответила Миа или нет.
Семантический поиск (RAG) живёт отдельно в vector_store.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from dataclasses import dataclass
from typing import Optional

from config import settings
from mia.core import time_utils

logger = logging.getLogger(__name__)


@dataclass
class StoredMessage:
    id: int
    chat_id: int
    chat_title: str
    user_id: Optional[int]
    user_name: str
    text: str
    msg_type: str
    is_authoritative: bool
    created_at: str


_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id             INTEGER NOT NULL,
    chat_title          TEXT DEFAULT '',
    user_id             INTEGER,
    user_name           TEXT DEFAULT '',
    text                TEXT NOT NULL,
    msg_type            TEXT DEFAULT 'text',
    telegram_message_id INTEGER,
    is_authoritative    INTEGER DEFAULT 0,
    created_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);

CREATE TABLE IF NOT EXISTS reminders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id     INTEGER NOT NULL,
    user_id     INTEGER,
    text        TEXT NOT NULL,
    remind_at   TEXT NOT NULL,
    is_broadcast INTEGER DEFAULT 0,
    fired       INTEGER DEFAULT 0,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reminders_time ON reminders(remind_at, fired);
"""


class Database:
    def __init__(self, db_path: Optional[str] = None) -> None:
        settings.ensure_dirs()
        self.db_path = str(db_path or settings.DB_PATH)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
        logger.info("База данных инициализирована: %s", self.db_path)

    # --- Сообщения ---
    def add_message(
        self,
        chat_id: int,
        text: str,
        chat_title: str = "",
        user_id: Optional[int] = None,
        user_name: str = "",
        msg_type: str = "text",
        telegram_message_id: Optional[int] = None,
        is_authoritative: bool = False,
    ) -> int:
        with self._lock:
            cur = self._conn.execute(
                """INSERT INTO messages
                   (chat_id, chat_title, user_id, user_name, text, msg_type,
                    telegram_message_id, is_authoritative, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    chat_id,
                    chat_title,
                    user_id,
                    user_name,
                    text,
                    msg_type,
                    telegram_message_id,
                    1 if is_authoritative else 0,
                    time_utils.iso_now(),
                ),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def recent_messages(self, chat_id: int, limit: int = 10) -> list[StoredMessage]:
        """Последние сообщения конкретного чата (для короткого контекста)."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT * FROM messages WHERE chat_id = ?
                   ORDER BY id DESC LIMIT ?""",
                (chat_id, limit),
            ).fetchall()
        return [self._row_to_message(r) for r in reversed(rows)]

    def count_messages(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS c FROM messages").fetchone()
        return int(row["c"])

    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> StoredMessage:
        return StoredMessage(
            id=row["id"],
            chat_id=row["chat_id"],
            chat_title=row["chat_title"],
            user_id=row["user_id"],
            user_name=row["user_name"],
            text=row["text"],
            msg_type=row["msg_type"],
            is_authoritative=bool(row["is_authoritative"]),
            created_at=row["created_at"],
        )

    def close(self) -> None:
        with self._lock:
            self._conn.close()
