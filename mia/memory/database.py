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


@dataclass
class StoredDocument:
    id: int
    chat_id: int
    chat_title: str
    user_id: Optional[int]
    user_name: str
    file_name: str
    mime: str
    stored_path: str
    text_path: str
    kind: str
    needs_ocr: bool
    char_count: int
    telegram_message_id: Optional[int]
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

CREATE TABLE IF NOT EXISTS documents (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id             INTEGER NOT NULL,
    chat_title          TEXT DEFAULT '',
    user_id             INTEGER,
    user_name           TEXT DEFAULT '',
    file_name           TEXT DEFAULT '',
    mime                TEXT DEFAULT '',
    stored_path         TEXT DEFAULT '',
    text_path           TEXT DEFAULT '',
    kind                TEXT DEFAULT '',
    needs_ocr           INTEGER DEFAULT 0,
    char_count          INTEGER DEFAULT 0,
    telegram_message_id INTEGER,
    created_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_chat ON documents(chat_id);
CREATE INDEX IF NOT EXISTS idx_documents_tgmsg ON documents(telegram_message_id);
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

    # --- Документы ---
    def add_document(
        self,
        chat_id: int,
        file_name: str,
        stored_path: str,
        text_path: str = "",
        chat_title: str = "",
        user_id: Optional[int] = None,
        user_name: str = "",
        mime: str = "",
        kind: str = "",
        needs_ocr: bool = False,
        char_count: int = 0,
        telegram_message_id: Optional[int] = None,
    ) -> int:
        with self._lock:
            cur = self._conn.execute(
                """INSERT INTO documents
                   (chat_id, chat_title, user_id, user_name, file_name, mime,
                    stored_path, text_path, kind, needs_ocr, char_count,
                    telegram_message_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    chat_id, chat_title, user_id, user_name, file_name, mime,
                    stored_path, text_path, kind, 1 if needs_ocr else 0, char_count,
                    telegram_message_id, time_utils.iso_now(),
                ),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def get_document(self, doc_id: int) -> Optional[StoredDocument]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM documents WHERE id = ?", (doc_id,)
            ).fetchone()
        return self._row_to_document(row) if row else None

    def get_document_by_tg_message(
        self, chat_id: int, telegram_message_id: int
    ) -> Optional[StoredDocument]:
        with self._lock:
            row = self._conn.execute(
                """SELECT * FROM documents
                   WHERE chat_id = ? AND telegram_message_id = ?
                   ORDER BY id DESC LIMIT 1""",
                (chat_id, telegram_message_id),
            ).fetchone()
        return self._row_to_document(row) if row else None

    def latest_document(self, chat_id: int) -> Optional[StoredDocument]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM documents WHERE chat_id = ? ORDER BY id DESC LIMIT 1",
                (chat_id,),
            ).fetchone()
        return self._row_to_document(row) if row else None

    @staticmethod
    def _row_to_document(row: sqlite3.Row) -> StoredDocument:
        return StoredDocument(
            id=row["id"],
            chat_id=row["chat_id"],
            chat_title=row["chat_title"],
            user_id=row["user_id"],
            user_name=row["user_name"],
            file_name=row["file_name"],
            mime=row["mime"],
            stored_path=row["stored_path"],
            text_path=row["text_path"],
            kind=row["kind"],
            needs_ocr=bool(row["needs_ocr"]),
            char_count=row["char_count"],
            telegram_message_id=row["telegram_message_id"],
            created_at=row["created_at"],
        )

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
