"""Сводка по документу: извлечение полей через LLM и сборка xlsx.

Сводка формируется ТОЛЬКО по запросу пользователя. Помимо отдельного файла
сводки, данные добавляются в общий накопительный реестр (data/Реестр.xlsx),
близкий по смыслу к вашему «Реестру документов по сопровождению СМР».
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from config import settings
from mia.core import time_utils
from mia.core.llm import LLMClient, LLMError, llm_client
from mia.documents.extractor import clip_text, extract_text
from mia.memory.database import StoredDocument

logger = logging.getLogger(__name__)

# Поля сводки (порядок = порядок колонок в реестре)
FIELDS: list[tuple[str, str]] = [
    ("object", "Объект"),
    ("project_code", "Шифр проекта"),
    ("work_type", "Вид работ"),
    ("tech_conditions", "ТУ"),
    ("organization", "Организация (СО)"),
    ("doc_type", "Тип документа"),
    ("doc_number", "Номер документа"),
    ("doc_date", "Дата документа"),
    ("key_amounts", "Ключевые суммы / объёмы"),
    ("section", "Участок"),
    ("status", "Статус"),
    ("summary", "Краткое содержание"),
    ("missing", "Чего не хватает / на что обратить внимание"),
]

_MAX_TEXT = 16000  # символов текста документа в промпт

_EXTRACT_PROMPT = """Ты — инженер ПТО в компании, строящей сети связи \
(кабельная канализация и кабели). Проанализируй текст документа и извлеки поля.

Текст документа (может быть обрезан):
---
{text}
---

Верни ТОЛЬКО JSON без пояснений и markdown, со следующими ключами (если чего-то \
нет в документе — ставь пустую строку ""):
{{
  "object": "объект/адрес",
  "project_code": "шифр проекта",
  "work_type": "вид работ (например: демонтаж, прокладка кабеля, ККС)",
  "tech_conditions": "ТУ (технические условия), если упомянуты",
  "organization": "организация/заказчик/согласующий орган",
  "doc_type": "тип документа (КП, смета, договор, письмо, акт, ТУ, реестр и т.п.)",
  "doc_number": "номер документа",
  "doc_date": "дата документа",
  "key_amounts": "ключевые суммы и объёмы (кратко: итоговые стоимости, метраж и т.п.)",
  "section": "участок",
  "status": "статус, если указан",
  "summary": "краткое содержание документа в 2-4 предложениях на русском",
  "missing": "чего не хватает или на что обратить внимание (если очевидно)"
}}

ВАЖНО про суммы: бери их из строки «ИТОГО»/«Всего»/«Итого по смете» ДОСЛОВНО. \
Ничего не складывай и не считай сам. Если итоговой суммы в тексте нет — оставь \
пустую строку. Не выдумывай цифры."""


def _read_doc_text(doc: StoredDocument) -> str:
    if doc.text_path and Path(doc.text_path).exists():
        return Path(doc.text_path).read_text(encoding="utf-8", errors="replace")
    if doc.stored_path and Path(doc.stored_path).exists():
        return extract_text(doc.stored_path).text
    return ""


def _parse_json(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:]
    start = content.find("{")
    end = content.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(content[start:end])
        except json.JSONDecodeError:
            return {}
    return {}


def extract_fields(doc: StoredDocument, llm: Optional[LLMClient] = None) -> dict:
    llm = llm or llm_client
    text = _read_doc_text(doc)
    if not text.strip():
        return {"summary": "В документе не удалось извлечь текст (возможно, скан — нужен OCR)."}

    prompt = _EXTRACT_PROMPT.format(text=clip_text(text))
    try:
        content = llm.complete(
            system_prompt="Ты извлекаешь структурированные данные. Отвечай только JSON.",
            user_prompt=prompt,
            temperature=0.1,
            max_tokens=900,
        )
    except LLMError as e:
        logger.error("LLM ошибка при извлечении полей: %s", e)
        return {"summary": "Не удалось разобрать документ — модель недоступна."}

    data = _parse_json(content)
    if not data:
        data = {"summary": content[:1000]}
    return data


def _autosize(ws) -> None:
    for column_cells in ws.columns:
        length = 0
        col = column_cells[0].column_letter
        for cell in column_cells:
            if cell.value is not None:
                length = max(length, len(str(cell.value)))
        ws.column_dimensions[col].width = min(max(length + 2, 12), 80)


def build_summary_xlsx(doc: StoredDocument, fields: dict, dest_path: str) -> str:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Сводка"

    header_fill = PatternFill("solid", fgColor="1F7A4D")
    header_font = Font(bold=True, color="FFFFFF")

    ws["A1"] = "Сводка по документу"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"Файл: {doc.file_name}"
    ws["A3"] = f"Сформировано: {time_utils.human_now()}"

    row = 5
    ws.cell(row=row, column=1, value="Поле").fill = header_fill
    ws.cell(row=row, column=1).font = header_font
    ws.cell(row=row, column=2, value="Значение").fill = header_fill
    ws.cell(row=row, column=2).font = header_font
    row += 1

    for key, label in FIELDS:
        ws.cell(row=row, column=1, value=label).font = Font(bold=True)
        value = str(fields.get(key, "") or "")
        cell = ws.cell(row=row, column=2, value=value)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        row += 1

    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["B"].width = 80

    wb.save(dest_path)
    return dest_path


def append_to_registry(doc: StoredDocument, fields: dict) -> str:
    """Добавляет строку в общий накопительный реестр data/Реестр.xlsx."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill

    settings.ensure_dirs()
    registry_path = settings.DATA_DIR / "Реестр.xlsx"

    headers = ["Файл", "Добавлено"] + [label for _, label in FIELDS]

    if registry_path.exists():
        wb = openpyxl.load_workbook(str(registry_path))
        ws = wb.active
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Реестр документов"
        header_fill = PatternFill("solid", fgColor="1F7A4D")
        header_font = Font(bold=True, color="FFFFFF")
        for col, title in enumerate(headers, start=1):
            c = ws.cell(row=1, column=1 + col - 1, value=title)
            c.fill = header_fill
            c.font = header_font

    values = [doc.file_name, time_utils.now().strftime("%d.%m.%Y %H:%M")]
    values += [str(fields.get(key, "") or "") for key, _ in FIELDS]
    ws.append(values)

    _autosize(ws)
    wb.save(str(registry_path))
    return str(registry_path)


def summarize(doc: StoredDocument, llm: Optional[LLMClient] = None) -> dict:
    """Полный цикл: извлечь поля, собрать xlsx-сводку и обновить реестр.

    Возвращает {fields, summary_path, registry_path, text_summary}.
    """
    fields = extract_fields(doc, llm=llm)

    ts = time_utils.now().strftime("%Y%m%d-%H%M%S")
    safe_name = Path(doc.file_name).stem or "document"
    summary_path = str(settings.UPLOADS_DIR / f"Сводка_{safe_name}_{ts}.xlsx")
    build_summary_xlsx(doc, fields, summary_path)

    registry_path = append_to_registry(doc, fields)

    return {
        "fields": fields,
        "summary_path": summary_path,
        "registry_path": registry_path,
        "text_summary": fields.get("summary", ""),
    }
