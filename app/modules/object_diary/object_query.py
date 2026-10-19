"""ObjectQueryRouter — ответы на вопросы по объектам в свободной форме.

Распознаёт интент (расходы / закупки / ограничения / наличие документа) и
объект по названию (с учётом падежей), затем отвечает данными из SQLite.
Не требует ни команд, ни LLM. Если запрос не распознан — возвращает ``None``,
и бот отвечает как обычно (диалог/делегирование).

Примеры:
    «Миа, что мы закупили по Судакова?»      → закупки (invoices)
    «Миа, сколько потрачено на Профсоюзную?» → расходы (SUM invoices.amount)
    «Миа, что нас держит по Лодочной?»       → ограничения (constraints)
    «Миа, есть ли ОАТИ по Новопоселковой?»   → наличие документа/ограничения
"""

from __future__ import annotations

import logging
import re
from typing import Any, List, Optional, Tuple

from app.modules.storage.database import get_db_connection

logger = logging.getLogger(__name__)

SPEND_KEYWORDS = (
    "сколько потрачено",
    "сколько ушло",
    "сколько израсходовано",
    "потрачено",
    "расходы",
    "затраты",
    "освоено",
)
PURCHASE_KEYWORDS = (
    "что мы закупили",
    "что закупили",
    "что купили",
    "закупили",
    "закупки",
    "что привезли",
    "поставки",
    "что поставлено",
)
BLOCK_KEYWORDS = (
    "что нас держит",
    "что держит",
    "что мешает",
    "что блокирует",
    "блокирует",
    "ограничения",
    "чего не хватает",
    "что не хватает",
    "что тормозит",
)
DOC_TRIGGERS = ("есть ли", "получено ли", "получен ли", "есть")

_STOPWORDS = {
    "миа", "объект", "объекту", "объекте", "объекта", "по", "на", "за", "у",
    "для", "что", "мы", "нас", "нам", "есть", "ли", "сколько", "и", "или",
    "в", "во", "с", "со", "к", "ко", "о", "об", "все", "всё", "нам", "мне",
    "потрачено", "держит", "закупили", "купили", "закупки", "привезли",
    "поставки", "поставлено", "расходы", "затраты", "освоено", "мешает",
    "блокирует", "ограничения", "тормозит", "хватает", "израсходовано",
    "получено", "получен", "ушло", "про", "это",
}

_VOWELS = "аеёиоуыэюяйь"


def _stem(word: str) -> str:
    """Грубо убрать падежное окончание (для сопоставления названий)."""
    w = word.lower().replace("ё", "е").strip("«»\"'.,!?")
    for _ in range(2):
        if len(w) > 4 and w[-1] in _VOWELS:
            w = w[:-1]
        else:
            break
    return w


def _norm(text: str) -> str:
    """Нормализация для сравнения по-русски (casefold понимает кириллицу)."""
    return (text or "").replace("ё", "е").replace("Ё", "Е").casefold()


def _money(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


class ObjectQueryRouter:
    """Маршрутизатор запросов по объектам (без команд и LLM)."""

    def query(self, text: str) -> Optional[str]:
        text = (text or "").strip()
        if not text:
            return None
        low = text.lower()

        try:
            with get_db_connection() as conn:
                docs = self._match_doc(low)
                if docs is not None:
                    return self._answer_doc(conn, text, low, *docs)

                if any(k in low for k in SPEND_KEYWORDS):
                    return self._answer_spend(conn, text)
                if any(k in low for k in PURCHASE_KEYWORDS):
                    return self._answer_purchases(conn, text)
                if any(k in low for k in BLOCK_KEYWORDS):
                    return self._answer_blockers(conn, text)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("ObjectQueryRouter failed: %s", e)
            return None
        return None

    # ------------------------------------------------------------------
    # Определение документа («есть ли ОАТИ по ...») 
    # ------------------------------------------------------------------
    def _match_doc(self, low: str) -> Optional[Tuple[str, str]]:
        if not any(low.startswith(t) or f" {t} " in f" {low} " for t in DOC_TRIGGERS):
            return None
        m = re.search(
            r"(?:есть\s+ли|получено\s+ли|получен\s+ли|есть)\s+"
            r"([^,?.]+?)\s+(?:по|на|за|у|для)\s+(.+)",
            low,
        )
        if not m:
            return None
        doc_term = m.group(1).strip()
        object_phrase = m.group(2).strip()
        if not doc_term:
            return None
        return doc_term, object_phrase

    # ------------------------------------------------------------------
    # Сопоставление объекта
    # ------------------------------------------------------------------
    def _tokenize(self, phrase: str) -> List[str]:
        return re.findall(r"[А-Яа-яЁёA-Za-z][\w\-]+", phrase)

    def _resolve_object(
        self, conn: Any, phrase: str
    ) -> Optional[Tuple[str, str]]:
        tokens = [t for t in self._tokenize(phrase) if len(t) >= 4]
        rows = conn.execute(
            "SELECT object_id, object_name FROM objects"
        ).fetchall()
        rows = sorted(rows, key=lambda r: len(r["object_name"] or ""))
        for tok in tokens:
            if tok.lower() in _STOPWORDS:
                continue
            stem = _norm(_stem(tok))
            if len(stem) < 4:
                continue
            for r in rows:
                if stem in _norm(r["object_name"]):
                    return r["object_id"], r["object_name"]
        return None

    def _object_from_text(self, conn: Any, text: str) -> Optional[Tuple[str, str]]:
        m = re.search(
            r"(?:по|на|за|у|для)\s+([А-ЯЁA-Zа-яёa-z0-9][^,?.]*)", text
        )
        if m and (resolved := self._resolve_object(conn, m.group(1))):
            return resolved
        return self._resolve_object(conn, text)

    # ------------------------------------------------------------------
    # Ответы
    # ------------------------------------------------------------------
    def _answer_spend(self, conn: Any, text: str) -> Optional[str]:
        obj = self._object_from_text(conn, text)
        if not obj:
            return None
        oid, name = obj
        row = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(amount), 0) AS total "
            "FROM invoices WHERE object_id = ?",
            (oid,),
        ).fetchone()
        if not row or not row["n"]:
            return f"По объекту «{name}» операций по счетам пока не найдено."
        lines = [f"По объекту «{name}» потрачено {_money(row['total'])} ₽ (счетов: {row['n']})."]
        top = conn.execute(
            "SELECT description, amount FROM invoices WHERE object_id = ? "
            "ORDER BY amount DESC LIMIT 3",
            (oid,),
        ).fetchall()
        for r in top:
            desc = (r["description"] or "без описания").strip()
            lines.append(f"  • {desc} — {_money(r['amount'])} ₽")
        return "\n".join(lines)

    def _answer_purchases(self, conn: Any, text: str) -> Optional[str]:
        obj = self._object_from_text(conn, text)
        if not obj:
            return None
        oid, name = obj
        rows = conn.execute(
            "SELECT description, amount, date FROM invoices WHERE object_id = ? "
            "ORDER BY date DESC LIMIT 10",
            (oid,),
        ).fetchall()
        if not rows:
            return f"По объекту «{name}» закупок/счетов пока не найдено."
        lines = [f"По объекту «{name}» закупки (последние {len(rows)}):"]
        for r in rows:
            desc = (r["description"] or "без описания").strip()
            lines.append(f"  • {desc} — {_money(r['amount'])} ₽ ({r['date']})")
        return "\n".join(lines)

    def _answer_blockers(self, conn: Any, text: str) -> Optional[str]:
        obj = self._object_from_text(conn, text)
        if not obj:
            return None
        oid, name = obj
        rows = conn.execute(
            "SELECT constraint_name, description, severity_level, status, deadline "
            "FROM constraints WHERE object_id = ? "
            "AND upper(status) NOT IN ('SATISFIED', 'RESOLVED', 'IGNORED', 'DONE') "
            "ORDER BY CASE upper(severity_level) "
            "WHEN 'CRITICAL' THEN 0 WHEN 'BLOCKER' THEN 0 WHEN 'MAJOR' THEN 1 "
            "ELSE 2 END, constraint_name",
            (oid,),
        ).fetchall()
        if not rows:
            return f"По объекту «{name}» активных ограничений нет — ничего не держит."
        lines = [f"По объекту «{name}» держат {len(rows)} ограничений:"]
        for r in rows:
            sev = (r["severity_level"] or "").strip()
            suffix = f" [{sev}]" if sev else ""
            deadline = f" (срок {(r['deadline'] or '')[:10]})" if r["deadline"] else ""
            lines.append(f"  • {r['constraint_name']}{suffix}{deadline}")
        return "\n".join(lines)

    def _answer_doc(
        self, conn: Any, text: str, low: str, doc_term: str, object_phrase: str
    ) -> Optional[str]:
        obj = self._resolve_object(conn, object_phrase)
        if not obj:
            return None
        oid, name = obj
        pattern = _norm(doc_term)

        items: List[str] = []
        for r in conn.execute(
            "SELECT constraint_name, description, status, deadline FROM constraints "
            "WHERE object_id = ?",
            (oid,),
        ).fetchall():
            haystack = _norm(r["constraint_name"]) + " " + _norm(r["description"])
            if pattern in haystack:
                deadline = (
                    f" (срок {(r['deadline'] or '')[:10]})" if r["deadline"] else ""
                )
                items.append(f"  • {r['constraint_name']}: {r['status']}{deadline}")

        for r in conn.execute(
            "SELECT vd.doc_type, vd.doc_name, vd.status FROM virtual_documents vd "
            "JOIN objects o ON o.diary_id = vd.diary_id WHERE o.object_id = ?",
            (oid,),
        ).fetchall():
            haystack = _norm(r["doc_name"]) + " " + _norm(r["doc_type"])
            if pattern in haystack:
                items.append(f"  • {r['doc_name']} ({r['doc_type']}): {r['status']}")

        if not items:
            return f"По объекту «{name}» упоминаний «{doc_term}» не нашла."
        header = f"По объекту «{name}» по запросу «{doc_term}»:"
        return "\n".join([header] + items)
