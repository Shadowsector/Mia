"""Извлечение текста из документов: docx, xlsx, pdf, txt/csv.

PDF-сканы (без текстового слоя) помечаются needs_ocr — распознавание
подключим отдельным этапом.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ExtractResult:
    text: str
    kind: str          # docx | xlsx | pdf | text | unknown
    needs_ocr: bool = False
    note: str = ""

    @property
    def has_text(self) -> bool:
        return bool(self.text and self.text.strip())


def _extract_docx(path: Path) -> ExtractResult:
    import docx  # python-docx

    document = docx.Document(str(path))
    parts: list[str] = []
    for para in document.paragraphs:
        if para.text.strip():
            parts.append(para.text.strip())
    # Таблицы
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    return ExtractResult(text="\n".join(parts), kind="docx")


def _extract_xlsx(path: Path, max_rows_per_sheet: int = 2000) -> ExtractResult:
    import warnings

    import openpyxl

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    parts: list[str] = []
    for ws in wb.worksheets:
        parts.append(f"### Лист: {ws.title}")
        count = 0
        for row in ws.iter_rows(values_only=True):
            values = [str(v) for v in row if v is not None and str(v).strip()]
            if values:
                parts.append(" | ".join(values))
                count += 1
            if count >= max_rows_per_sheet:
                parts.append("… (лист обрезан)")
                break
    wb.close()
    return ExtractResult(text="\n".join(parts), kind="xlsx")


def _extract_xls(path: Path, max_rows_per_sheet: int = 2000) -> ExtractResult:
    import xlrd  # старый .xls

    book = xlrd.open_workbook(str(path))
    parts: list[str] = []
    for sheet in book.sheets():
        parts.append(f"### Лист: {sheet.name}")
        rows = min(sheet.nrows, max_rows_per_sheet)
        for rx in range(rows):
            values = []
            for v in sheet.row_values(rx):
                if v is None:
                    continue
                if isinstance(v, float) and v.is_integer():
                    v = int(v)
                s = str(v).strip()
                if s:
                    values.append(s)
            if values:
                parts.append(" | ".join(values))
        if sheet.nrows > max_rows_per_sheet:
            parts.append("… (лист обрезан)")
    return ExtractResult(text="\n".join(parts), kind="xls")


def _extract_pdf(path: Path) -> ExtractResult:
    import fitz  # PyMuPDF

    doc = fitz.open(str(path))
    parts: list[str] = []
    for page in doc:
        text = page.get_text().strip()
        if text:
            parts.append(text)
    doc.close()
    full = "\n".join(parts)
    if not full.strip():
        return ExtractResult(
            text="",
            kind="pdf",
            needs_ocr=True,
            note="PDF без текстового слоя (вероятно скан). Нужен OCR.",
        )
    return ExtractResult(text=full, kind="pdf")


def _extract_text_file(path: Path) -> ExtractResult:
    data = path.read_bytes()
    return ExtractResult(text=data.decode("utf-8", errors="replace"), kind="text")


def extract_text(path: str | Path) -> ExtractResult:
    path = Path(path)
    ext = path.suffix.lower()
    try:
        if ext == ".docx":
            return _extract_docx(path)
        if ext in (".xlsx", ".xlsm"):
            return _extract_xlsx(path)
        if ext == ".xls":
            return _extract_xls(path)
        if ext == ".pdf":
            return _extract_pdf(path)
        if ext in (".txt", ".csv", ".md"):
            return _extract_text_file(path)
    except Exception as e:
        logger.exception("Ошибка извлечения текста из %s", path)
        return ExtractResult(text="", kind="unknown", note=f"Ошибка чтения: {e}")

    return ExtractResult(
        text="",
        kind="unknown",
        note=f"Формат {ext or '—'} пока не поддерживается.",
    )
