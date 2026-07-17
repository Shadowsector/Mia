"""OCR сканов через локальную vision-модель Ollama (без внешних установок).

Страницы PDF рендерятся в изображения (PyMuPDF) и распознаются vision-моделью.
OCR запускается лениво — только когда по скану реально запросили сводку или
задали вопрос, чтобы не грузить систему на каждый загруженный файл.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from config import settings
from mia.core.llm import LLMClient, LLMError, llm_client
from mia.memory.database import Database, StoredDocument

logger = logging.getLogger(__name__)

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}

_OCR_PROMPT = (
    "Это скан документа строительной компании (сети связи). Извлеки ВЕСЬ текст "
    "с изображения максимально дословно и по порядку, сохраняя таблицы в виде "
    "строк с разделителями. Не добавляй пояснений — только распознанный текст."
)


def _render_pdf(path: Path) -> list[bytes]:
    import fitz  # PyMuPDF

    images: list[bytes] = []
    doc = fitz.open(str(path))
    try:
        for i, page in enumerate(doc):
            if i >= settings.OCR_MAX_PAGES:
                break
            pix = page.get_pixmap(dpi=settings.OCR_DPI)
            images.append(pix.tobytes("png"))
    finally:
        doc.close()
    return images


def _load_image(path: Path) -> list[bytes]:
    return [path.read_bytes()]


def ocr_file(path: str | Path, llm: Optional[LLMClient] = None) -> str:
    """Распознаёт текст со скана (PDF или изображение)."""
    llm = llm or llm_client
    path = Path(path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        images = _render_pdf(path)
    elif ext in _IMAGE_EXTS:
        images = _load_image(path)
    else:
        return ""

    parts: list[str] = []
    for idx, img in enumerate(images, 1):
        try:
            text = llm.chat_with_images(_OCR_PROMPT, [img])
        except LLMError as e:
            logger.error("OCR: ошибка vision-модели на стр. %s: %s", idx, e)
            break
        if text.strip():
            if len(images) > 1:
                parts.append(f"--- Страница {idx} ---")
            parts.append(text.strip())
    return "\n".join(parts)


def vision_available(llm: Optional[LLMClient] = None) -> bool:
    llm = llm or llm_client
    from config import runtime

    return runtime.get_active_vision_model() in llm.list_models()


def ensure_document_text(
    doc: StoredDocument, db: Database, llm: Optional[LLMClient] = None
) -> StoredDocument:
    """Гарантирует, что у документа есть текст: при необходимости запускает OCR
    и обновляет запись в БД. Возвращает актуальный документ."""
    if doc.char_count > 0 and doc.text_path and Path(doc.text_path).exists():
        return doc

    ext = Path(doc.stored_path).suffix.lower()
    if ext != ".pdf" and ext not in _IMAGE_EXTS:
        return doc
    if not doc.stored_path or not Path(doc.stored_path).exists():
        return doc

    if not vision_available(llm):
        logger.warning(
            "OCR недоступен: vision-модель не установлена в Ollama (%s).",
            settings.VISION_MODEL,
        )
        return doc

    logger.info("Запускаю OCR для документа: %s", doc.file_name)
    text = ocr_file(doc.stored_path, llm=llm)
    if not text.strip():
        return doc

    text_path = str(Path(doc.stored_path).with_suffix(Path(doc.stored_path).suffix + ".txt"))
    Path(text_path).write_text(text, encoding="utf-8")
    db.update_document_text(doc.id, text_path, len(text), needs_ocr=False)

    refreshed = db.get_document(doc.id)
    return refreshed or doc
