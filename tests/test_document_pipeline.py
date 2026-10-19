"""Tests for the document pipeline (parsers, extractor, RAG ingestion, Google Drive helpers)."""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.modules.storage.database import initialize_database, get_db_connection


@pytest.fixture(scope="module", autouse=True)
def db():
    initialize_database()
    yield


@pytest.fixture()
def suffix():
    import uuid

    return uuid.uuid4().hex[:8]


@pytest.fixture()
def digits():
    import uuid

    return str(uuid.uuid4().int)[:9]


class FakeEmbeddingFunction:
    """Deterministic embedding function so tests never call Ollama."""

    def __call__(self, input):
        return [[0.1, 0.2, 0.3] for _ in input]

    def embed_documents(self, input):
        return [[0.1, 0.2, 0.3] for _ in input]

    def embed_query(self, input):
        return [[0.1, 0.2, 0.3] for _ in input]

    @staticmethod
    def name():
        return "fake-embedding"


@pytest.fixture()
def fake_embedding(monkeypatch):
    import app.modules.rag.chroma_manager as chroma_module

    monkeypatch.setattr(
        chroma_module.embedding_functions,
        "OllamaEmbeddingFunction",
        lambda **kwargs: FakeEmbeddingFunction(),
    )
    return FakeEmbeddingFunction()


class FakeCollection:
    def __init__(self):
        self.added = []
        self.queries = []

    def add(self, ids, documents, metadatas):
        self.added.append({"ids": ids, "documents": documents, "metadatas": metadatas})

    def query(self, query_texts, n_results, where=None):
        self.queries.append({"query": query_texts[0], "n_results": n_results, "where": where})
        return {
            "ids": [["chunk_0"]],
            "documents": [["найденный текст"]],
            "metadatas": [[{"source_file": "a.txt"}]],
            "distances": [[0.12]],
        }


class TestDocumentParserFactory:
    @pytest.fixture()
    def factory(self):
        from app.modules.document_parser import DocumentParserFactory

        return DocumentParserFactory()

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("doc.pdf", "pdf"),
            ("doc.docx", "word"),
            ("doc.doc", "word"),
            ("doc.xlsx", "excel"),
            ("doc.xls", "excel"),
            ("doc.txt", "text"),
            ("doc.md", "text"),
        ],
    )
    def test_get_parser_by_extension(self, factory, name, expected):
        parser = factory.get_parser(name)
        assert parser is not None
        assert parser.parser_name == expected

    def test_unknown_extension_has_no_parser(self, factory):
        assert factory.get_parser("file.zzz") is None

    def test_parse_document_without_parser(self, factory):
        result = factory.parse_document("file.zzz")
        assert result["success"] is False
        assert "No parser available" in result["error"]

    def test_parse_text_file(self, factory, tmp_path):
        path = tmp_path / "note.txt"
        path.write_text("Первая строка\nВторая строка", encoding="utf-8")

        result = factory.parse_document(path)
        assert result["success"] is True
        assert "Первая строка" in result["text"]
        assert result["metadata"]["line_count"] == 2
        assert result["metadata"]["encoding"] == "utf-8"
        assert result["file_size"] > 0

    def test_extract_text_convenience_functions(self, tmp_path):
        from app.modules.document_parser import extract_text, parse_document

        path = tmp_path / "note.txt"
        path.write_text("Текст", encoding="utf-8")

        assert extract_text(path) == "Текст"
        assert parse_document(path)["success"] is True

    def test_text_parser_missing_file(self, tmp_path):
        from app.modules.document_parser import TextParser

        result = TextParser().parse(tmp_path / "missing.txt")
        assert result["success"] is False
        assert result["text"] == ""

    def test_text_parser_extract_text(self, tmp_path):
        from app.modules.document_parser import TextParser

        path = tmp_path / "note.md"
        path.write_text("# Заголовок", encoding="utf-8")
        assert TextParser().extract_text(path) == "# Заголовок"

    def test_base_parser_requires_implementation(self):
        from app.modules.document_parser import DocumentParser

        parser = DocumentParser()
        with pytest.raises(NotImplementedError):
            parser.parse("x")
        with pytest.raises(NotImplementedError):
            parser.extract_text("x")

    def test_pdf_parser_roundtrip(self, factory, tmp_path):
        fitz = pytest.importorskip("fitz")

        path = tmp_path / "doc.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Contract text")
        doc.save(str(path))
        doc.close()

        result = factory.parse_document(path)
        assert result["success"] is True
        assert result["metadata"]["page_count"] == 1
        assert "Contract text" in result["text"]
        assert len(result["pages"]) == 1

    def test_pdf_parser_invalid_file(self, tmp_path):
        from app.modules.document_parser import PDFParser

        bad = tmp_path / "bad.pdf"
        bad.write_bytes(b"not a pdf")
        result = PDFParser().parse(bad)
        assert result["success"] is False

    def test_word_parser_roundtrip(self, factory, tmp_path):
        docx = pytest.importorskip("docx")

        path = tmp_path / "doc.docx"
        document = docx.Document()
        document.add_paragraph("Первый абзац")
        document.add_paragraph("Второй абзац")
        table = document.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "A"
        table.cell(0, 1).text = "B"
        document.save(str(path))

        result = factory.parse_document(path)
        assert result["success"] is True
        assert "Первый абзац" in result["text"]
        assert result["metadata"]["paragraph_count"] == 2
        assert result["metadata"]["table_count"] == 1
        assert result["tables"] == [[["A", "B"]]]

    def test_excel_parser_roundtrip(self, factory, tmp_path):
        openpyxl = pytest.importorskip("openpyxl")

        path = tmp_path / "doc.xlsx"
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Смета"
        sheet.append(["Наименование", "Сумма"])
        sheet.append(["Кабель", 1000])
        workbook.save(str(path))

        result = factory.parse_document(path)
        assert result["success"] is True
        assert result["metadata"]["sheet_names"] == ["Смета"]
        assert "Кабель" in result["text"]
        assert result["sheets"][0]["row_count"] == 2

    def test_image_parser_without_tesseract(self, tmp_path):
        from app.modules.document_parser import ImageParser

        parser = ImageParser()
        if parser.tesseract_available:
            pytest.skip("Tesseract is installed")

        result = parser.parse(tmp_path / "img.png")
        assert result["success"] is False
        assert "Tesseract OCR not available" in result["error"]


class TestDocumentInfoExtractor:
    @pytest.fixture()
    def extractor(self):
        from app.modules.document_info_extractor import DocumentInfoExtractor

        return DocumentInfoExtractor()

    def test_financials_with_thousands_separators(self, extractor):
        result = extractor.extract_financials(
            "Сумма: 1,500,000.50 руб. Аванс 250 000 руб. Итого: 2.000.000,00 руб."
        )
        assert 1500000.5 in result["amounts"]
        assert 250000.0 in result["amounts"]
        assert 2000000.0 in result["amounts"]
        assert result["total_amount"] == 2000000.0
        assert result["currency"] == "RUB"
        assert result["vat_included"] is False

    def test_financials_vat_and_currency(self, extractor):
        result = extractor.extract_financials("Стоимость 1000 USD, в том числе НДС")
        assert result["amounts"] == [1000.0]
        assert result["vat_included"] is True

    def test_financials_empty(self, extractor):
        result = extractor.extract_financials("Нет денег")
        assert result == {
            "amounts": [],
            "total_amount": None,
            "currency": "RUB",
            "vat_included": False,
        }

    def test_dates_dd_mm_yyyy(self, extractor):
        result = extractor.extract_dates("Подписан 15.03.2024")
        assert "2024-03-15T00:00:00" in result["dates_found"]

    def test_dates_iso(self, extractor):
        result = extractor.extract_dates("Дата 2024-09-30")
        assert "2024-09-30T00:00:00" in result["dates_found"]

    def test_dates_russian_month(self, extractor):
        result = extractor.extract_dates("Срок 15 марта 2024")
        assert "2024-03-15T00:00:00" in result["dates_found"]

    def test_contract_and_completion_dates(self, extractor):
        text = "Дата договора: 15.03.2024. Срок выполнения: 30.09.2024."
        result = extractor.extract_dates(text)
        assert result["contract_date"] == "2024-03-15T00:00:00"
        assert result["completion_date"] == "2024-09-30T00:00:00"
        assert result["deadlines"] == ["2024-09-30T00:00:00"]

    def test_invalid_date_skipped(self, extractor):
        assert extractor.extract_dates("99.99.2024")["dates_found"] == []

    def test_materials(self, extractor):
        result = extractor.extract_materials("Кабель ВВГнг 3x2.5 - 500 м, труба ПНД")
        names = [item["name"] for item in result["items"]]
        assert "ВВГнг" in names
        assert "ПНД" in names
        assert result["total_items"] == 2

    def test_materials_quantity(self, extractor):
        result = extractor.extract_materials("500 м кабель")
        assert result["items"] == [{"name": "500", "quantity": 500}]

    def test_contract_info(self, extractor):
        text = (
            "Договор №123-456\n"
            "Заказчик: ООО Ромашка\n"
            "Подрядчик: ООО Стройка\n"
            "Объект: Жилой дом 5\n"
        )
        result = extractor.extract_contract_info(text)
        assert result["contract_number"] == "123-456"
        assert result["customer"] == "ООО Ромашка"
        assert result["contractor"] == "ООО Стройка"
        assert result["object_name"] == "Жилой дом 5"

    def test_contract_info_empty(self, extractor):
        assert extractor.extract_contract_info("Ничего") == {
            "contract_number": None,
            "customer": None,
            "contractor": None,
            "object_name": None,
        }

    def test_extract_all_missing_file(self, extractor, tmp_path):
        result = extractor.extract_all(str(tmp_path / "missing.txt"))
        assert result["success"] is False
        assert result["error"] == "File not found"

    def test_extract_all_on_text_file(self, extractor, tmp_path):
        path = tmp_path / "contract.txt"
        path.write_text(
            "Договор №7\nЗаказчик: ООО Тест\nСумма: 10 000 руб.\nСрок выполнения: 01.12.2024",
            encoding="utf-8",
        )

        result = extractor.extract_all(str(path))
        assert result["success"] is True
        assert result["raw_text"]
        assert result["financials"]["total_amount"] == 10000.0
        assert result["contract"]["contract_number"] == "7"
        assert result["dates"]["completion_date"] == "2024-12-01T00:00:00"

    def test_extract_from_directory(self, extractor, tmp_path):
        (tmp_path / "b.txt").write_text("текст", encoding="utf-8")

        result = extractor.extract_from_directory(str(tmp_path))
        assert result["success"] is True
        assert result["total_files"] == 0
        assert result["successful"] == 0
        assert result["failed"] == 0

    def test_extract_from_missing_directory(self, extractor, tmp_path):
        result = extractor.extract_from_directory(str(tmp_path / "nope"))
        assert result["success"] is False


class TestDocumentIngestor:
    @pytest.fixture()
    def ingestor(self):
        from app.modules.document_parser import DocumentParserFactory
        from app.modules.rag.document_ingestor import DocumentIngestor

        obj = DocumentIngestor.__new__(DocumentIngestor)
        obj.chroma_manager = SimpleNamespace(collection=FakeCollection())
        obj.document_parser = DocumentParserFactory()
        obj.chunk_size = 1000
        obj.chunk_overlap = 200
        return obj

    def test_chunk_text_empty(self, ingestor):
        assert ingestor.chunk_text("") == []
        assert ingestor.chunk_text("   ") == []

    def test_chunk_text_short(self, ingestor):
        assert ingestor.chunk_text("Короткий текст") == ["Короткий текст"]

    def test_chunk_text_splits_long_text(self, ingestor):
        chunks = ingestor.chunk_text("a" * 2500)
        assert len(chunks) >= 3
        assert all(len(c) <= ingestor.chunk_size for c in chunks)

    def test_chunk_text_terminates_with_large_overlap(self):
        from app.modules.rag.document_ingestor import DocumentIngestor

        obj = DocumentIngestor.__new__(DocumentIngestor)
        obj.chunk_size = 50
        obj.chunk_overlap = 200

        chunks = obj.chunk_text("A. " + "b" * 200)
        assert chunks
        assert all(len(c) <= 50 for c in chunks)

    def test_chunk_text_prefers_sentence_boundary(self, ingestor):
        text = "Первое предложение. " + "b" * 2000
        chunks = ingestor.chunk_text(text)
        assert chunks[0].endswith(".")

    def test_ingest_document_missing_file(self, ingestor, tmp_path):
        result = ingestor.ingest_document(str(tmp_path / "missing.txt"))
        assert result == {"success": False, "error": "File not found"}

    def test_ingest_document_success(self, ingestor, tmp_path):
        path = tmp_path / "contract.txt"
        path.write_text("Текст договора. " * 200, encoding="utf-8")

        result = ingestor.ingest_document(
            str(path), object_id="OBJ-1", document_type="contract", metadata={"x": 1}
        )
        assert result["success"] is True
        assert result["chunks_added"] == len(ingestor.chroma_manager.collection.added[0]["ids"])
        assert result["object_id"] == "OBJ-1"

        payload = ingestor.chroma_manager.collection.added[0]
        assert payload["ids"][0] == "contract_chunk_0"
        assert payload["metadatas"][0]["object_id"] == "OBJ-1"
        assert payload["metadatas"][0]["document_type"] == "contract"
        assert payload["metadatas"][0]["chunk_index"] == 0
        assert payload["metadatas"][0]["x"] == 1

    def test_ingest_document_no_text(self, ingestor, tmp_path):
        path = tmp_path / "empty.txt"
        path.write_text("", encoding="utf-8")

        result = ingestor.ingest_document(str(path))
        assert result == {"success": False, "error": "No text extracted"}

    def test_ingest_directory(self, ingestor, tmp_path):
        (tmp_path / "договор_1.txt").write_text("Договор", encoding="utf-8")
        (tmp_path / "смета_1.txt").write_text("Смета", encoding="utf-8")
        (tmp_path / "random.zzz").write_text("x", encoding="utf-8")

        result = ingestor.ingest_directory(str(tmp_path), object_id="OBJ-2")
        assert result["total_files"] == 2
        assert result["successful"] == 2
        assert result["failed"] == 0

    def test_ingest_missing_directory(self, ingestor, tmp_path):
        result = ingestor.ingest_directory(str(tmp_path / "nope"))
        assert result["success"] is False
        assert result["error"] == "Directory not found"

    def test_search_similar_documents(self, ingestor):
        results = ingestor.search_similar_documents("договор", object_id="OBJ-1")
        assert results == [
            {
                "text": "найденный текст",
                "metadata": {"source_file": "a.txt"},
                "distance": 0.12,
            }
        ]
        assert ingestor.chroma_manager.collection.queries[0]["where"] == {"object_id": "OBJ-1"}

    def test_search_similar_documents_no_filters(self, ingestor):
        ingestor.search_similar_documents("договор")
        assert ingestor.chroma_manager.collection.queries[0]["where"] is None


class TestStructuredExcelParser:
    @pytest.fixture()
    def parser(self):
        from app.modules.rag.structured_excel_parser import StructuredExcelParser

        return StructuredExcelParser()

    @pytest.fixture()
    def workbook(self, tmp_path):
        pd = pytest.importorskip("pandas")
        path = tmp_path / "estimate.xlsx"
        df = pd.DataFrame(
            {
                "Наименование": ["Кабель", "Труба"],
                "Количество": [10, 20],
                "Итого": [1000.0, 2000.0],
            }
        )
        df.to_excel(path, index=False, sheet_name="Смета")
        return path

    def test_missing_file(self, parser, tmp_path):
        result = parser.parse_excel_file(str(tmp_path / "missing.xlsx"))
        assert result == {"success": False, "error": "File not found"}

    def test_parse_excel(self, parser, workbook):
        result = parser.parse_excel_file(str(workbook))
        assert result["success"] is True
        assert result["total_sheets"] == 1

        sheet = result["sheets"]["Смета"]
        assert sheet["rows"] == 2
        assert sheet["columns"] == 3
        assert sheet["column_names"] == ["Наименование", "Количество", "Итого"]
        assert sheet["numeric_columns"] == ["Количество", "Итого"]
        assert sheet["column_statistics"]["Итого"]["sum"] == 3000.0
        assert sheet["records"][0]["Наименование"] == "Кабель"
        assert "| Наименование |" in sheet["markdown_table"]
        assert json.loads(sheet["json_data"])[1]["Количество"] == 20

    def test_markdown_fallback(self, parser):
        pd = pytest.importorskip("pandas")

        df = pd.DataFrame({"a": [1, None], "b": ["x|y", "z"]})
        table = parser._dataframe_to_markdown(df)
        lines = table.splitlines()
        assert lines[0] == "| a | b |"
        assert lines[1] == "| --- | --- |"
        assert "x\\|y" in lines[2]
        assert lines[3] == "|  | z |"

    def test_estimate_summary(self, parser, workbook):
        data = parser.parse_excel_file(str(workbook))
        summary = parser.extract_estimate_summary(data)
        assert summary["total_items"] == 2
        assert summary["total_amount"] == 3000.0
        assert summary["items"] == []

    def test_estimate_summary_invalid(self, parser):
        assert parser.extract_estimate_summary({"success": False}) == {
            "error": "Invalid structured data"
        }

    def test_to_rag_chunks(self, parser, workbook):
        data = parser.parse_excel_file(str(workbook))
        chunks = parser.to_rag_chunks(data, chunk_size=1)
        assert len(chunks) == 2
        assert chunks[0]["chunk_id"] == "estimate.xlsx_Смета_chunk_0"
        assert chunks[0]["total_chunks"] == 2
        assert chunks[0]["metadata"]["row_count"] == 1
        assert chunks[0]["metadata"]["chunk_type"] == "structured_excel"

    def test_to_rag_chunks_invalid(self, parser):
        assert parser.to_rag_chunks({"success": False}) == []

    def test_hybrid_rag_ingest_and_query(self, monkeypatch, workbook):
        import app.modules.rag.structured_excel_parser as module

        collection = FakeCollection()
        fake_manager = SimpleNamespace(collection=collection)
        monkeypatch.setattr(
            "app.modules.rag.chroma_manager.ChromaManager", lambda *a, **k: fake_manager
        )

        hybrid = module.HybridRAG()
        result = hybrid.ingest_excel_file(str(workbook), object_id="OBJ-X")
        assert result["success"] is True
        assert result["chunks_added"] == 1
        assert collection.added[0]["metadatas"][0]["object_id"] == "OBJ-X"
        assert "Excel chunk from Смета" in collection.added[0]["documents"][0]

        results = hybrid.query_structured_data("итого", object_id="OBJ-X")
        assert results[0]["text"] == "найденный текст"
        assert collection.queries[0]["where"] == {
            "chunk_type": "structured_excel",
            "object_id": "OBJ-X",
        }

    def test_hybrid_rag_ingest_missing_file(self, monkeypatch, tmp_path):
        import app.modules.rag.structured_excel_parser as module

        hybrid = module.HybridRAG()
        result = hybrid.ingest_excel_file(str(tmp_path / "missing.xlsx"))
        assert result["success"] is False


class TestChromaManager:
    @pytest.fixture()
    def manager(self, tmp_path, fake_embedding):
        from app.modules.rag.chroma_manager import ChromaManager

        return ChromaManager(persist_directory=str(tmp_path / "chroma"))

    def test_initialize_collection(self, manager):
        assert manager.collection_name == "object_diary_chunks"
        assert manager.collection is not None

    def test_add_and_search_within_object(self, manager):
        chunk_id = manager.add_chunk(
            "Текст договора", "OBJ-1", "doc-1", "CONTRACT", legal_entities=["ООО А"]
        )
        assert chunk_id == "doc-1_chunk_0"

        results = manager.search_within_object("договор", "OBJ-1")
        assert [r["chunk_id"] for r in results] == ["doc-1_chunk_0"]
        assert results[0]["metadata"]["legal_entities"] == '["ООО А"]'
        assert results[0]["metadata"]["is_current"] == 1

    def test_search_within_object_includes_outdated(self, manager):
        manager.add_chunk("Старый текст", "OBJ-2", "doc-2", "CONTRACT", is_current=False)
        assert manager.search_within_object("текст", "OBJ-2", only_current=False)
        assert manager.search_within_object("текст", "OBJ-2", only_current=True) == []

    def test_search_between_objects_without_filters(self, manager):
        manager.add_chunk("Общий текст", "OBJ-3", "doc-3", "FINANCIAL")
        assert manager.search_between_objects("текст")

    def test_search_with_rrf_weights(self, manager):
        manager.add_chunk("Текст", "OBJ-4", "doc-4", "CONTRACT")
        manager.add_chunk("Текст", "OBJ-4", "doc-5", "REFERENCE")

        results = manager.search_with_rrf("текст", object_id="OBJ-4")
        assert results[0]["metadata"]["doc_category"] == "CONTRACT"

    def test_update_chunk_metadata(self, manager):
        chunk_id = manager.add_chunk("Текст", "OBJ-5", "doc-6", "CONTRACT")
        assert manager.update_chunk_metadata(chunk_id, {"is_current": 0}) is True

        results = manager.search_within_object("текст", "OBJ-5", only_current=False)
        assert results[0]["metadata"]["is_current"] == 0

    def test_update_unknown_chunk_returns_false(self, manager):
        assert manager.update_chunk_metadata("nope_chunk_0", {"is_current": 0}) is False

    def test_delete_chunks_by_doc_and_object(self, manager):
        manager.add_chunk("a", "OBJ-6", "doc-7", "CONTRACT", chunk_index=0)
        manager.add_chunk("b", "OBJ-6", "doc-7", "CONTRACT", chunk_index=1)
        assert manager.delete_chunks_by_doc("doc-7") == 2
        assert manager.delete_chunks_by_doc("doc-7") == 0

        manager.add_chunk("c", "OBJ-7", "doc-8", "CONTRACT")
        assert manager.delete_chunks_by_object("OBJ-7") == 1
        assert manager.delete_chunks_by_object("OBJ-7") == 0

    def test_collection_stats(self, manager):
        manager.add_chunk("x", "OBJ-8", "doc-9", "CONTRACT")
        stats = manager.get_collection_stats()
        assert stats["collection_name"] == "object_diary_chunks"
        assert stats["total_chunks"] == 1
        assert stats["persist_directory"].endswith("chroma")

    def test_format_empty_results(self, manager):
        assert manager._format_results({"ids": [], "documents": [], "metadatas": []}) == []


class TestTempFileProcessor:
    class FakeDownloader:
        def __init__(self, text="Содержимое", success=True):
            self.text = text
            self.success = success
            self.calls = []

        def download_file(self, file_id, output_path, file_name):
            self.calls.append((file_id, output_path, file_name))
            if not self.success:
                return {"success": False, "error": "boom"}
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(self.text, encoding="utf-8")
            return {"success": True, "file_path": str(output_path), "file_name": file_name}

    class FakeRag:
        def __init__(self, fail=False):
            self.added = []
            self.fail = fail

        def add_document(self, doc_id, text, metadata):
            if self.fail:
                raise RuntimeError("rag down")
            self.added.append({"doc_id": doc_id, "text": text, "metadata": metadata})

    @pytest.fixture()
    def processor(self, tmp_path):
        from app.modules.google_drive.temp_file_processor import TempFileProcessor

        return TempFileProcessor(temp_dir=tmp_path / "temp")

    def test_process_google_drive_file(self, processor):
        rag = self.FakeRag()
        result = processor.process_google_drive_file(
            "FILE-1",
            "contract.txt",
            self.FakeDownloader("Текст договора"),
            rag,
            {"object_id": "OBJ-1"},
        )

        assert result["success"] is True
        reference = result["file_reference"]
        assert reference["source"] == "google_drive"
        assert reference["source_id"] == "FILE-1"
        assert reference["rag_added"] is True
        assert reference["text_length"] == len("Текст договора")
        assert reference["metadata"] == {"object_id": "OBJ-1"}
        assert rag.added[0]["metadata"]["object_id"] == "OBJ-1"
        assert rag.added[0]["metadata"]["source"] == "google_drive"
        assert list((processor.temp_dir).iterdir()) == []

    def test_process_google_drive_download_failure(self, processor):
        result = processor.process_google_drive_file(
            "FILE-2", "a.txt", self.FakeDownloader(success=False), self.FakeRag()
        )
        assert result["success"] is False
        assert result["error"] == "Download failed: boom"

    def test_process_google_drive_parse_failure(self, processor):
        result = processor.process_google_drive_file(
            "FILE-3", "a.zzz", self.FakeDownloader("x"), self.FakeRag()
        )
        assert result["success"] is False
        assert "Parse failed" in result["error"]

    def test_process_google_drive_rag_failure_keeps_reference(self, processor):
        result = processor.process_google_drive_file(
            "FILE-4", "a.txt", self.FakeDownloader("x"), self.FakeRag(fail=True)
        )
        assert result["success"] is True
        assert result["file_reference"]["rag_added"] is False

    def test_process_telegram_file(self, processor, tmp_path):
        path = tmp_path / "tg.txt"
        path.write_text("Из телеграма", encoding="utf-8")
        rag = self.FakeRag()

        result = processor.process_telegram_file(
            path, "tg.txt", "Чат объекта", "Денис", 42, rag
        )
        assert result["success"] is True
        assert result["file_reference"]["source"] == "telegram"
        assert result["file_reference"]["source_id"] == "42"
        assert "Денис" in result["file_reference"]["reference"]
        assert rag.added[0]["metadata"]["chat_title"] == "Чат объекта"
        assert path.exists()

    def test_process_telegram_file_parse_failure(self, processor, tmp_path):
        path = tmp_path / "tg.zzz"
        path.write_text("x", encoding="utf-8")
        result = processor.process_telegram_file(
            path, "tg.zzz", "Чат", "Денис", 1, self.FakeRag()
        )
        assert result["success"] is False
        assert "Parse failed" in result["error"]

    def test_cleanup_temp_files(self, processor):
        old = processor.temp_dir / "old.txt"
        old.write_text("x", encoding="utf-8")
        fresh = processor.temp_dir / "fresh.txt"
        fresh.write_text("x", encoding="utf-8")

        past = time.time() - 100000
        os.utime(old, (past, past))

        processor.cleanup_temp_files(max_age_hours=24)
        assert old.exists() is False
        assert fresh.exists() is True

    def test_temp_path_is_unique(self, processor):
        first = processor._get_temp_path("a/b.txt")
        second = processor._get_temp_path("a/b.txt")
        assert first.name.endswith("a_b.txt")
        assert "\\" not in first.name and "/" not in first.name
        assert first.parent == second.parent


class TestGoogleDriveScanner:
    @pytest.fixture()
    def scanner(self):
        from app.modules.google_drive.scanner import GoogleDriveScanner

        return GoogleDriveScanner("creds.json", "folder")

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("doc.pdf", "office_documents"),
            ("doc.dwg", "cad_drawings"),
            ("photo.jpg", "images"),
            ("backup.zip", "archives"),
            ("notes.txt", "text"),
            ("file.zzz", "other"),
        ],
    )
    def test_categorize_file_type(self, scanner, name, expected):
        assert scanner.categorize_file_type(name, "") == expected

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("Накладная 5.pdf", "invoice"),
            ("Паспорт объекта.pdf", "passport"),
            ("Проект дома.pdf", "project"),
            ("Договор 1.docx", "contract"),
            ("Смета.xlsx", "estimate"),
            ("Просто файл.pdf", "unknown"),
        ],
    )
    def test_infer_document_type(self, scanner, name, expected):
        assert scanner.infer_document_type(name) == expected

    def test_analyze_file(self, scanner):
        result = scanner.analyze_file(
            {
                "id": "1",
                "name": "Договор 5.pdf",
                "mimeType": "application/pdf",
                "size": "10",
                "version": "3",
            }
        )
        assert result["file_type_category"] == "office_documents"
        assert result["document_type"] == "contract"
        assert result["has_version"] is True

    def test_statistics(self, scanner):
        scan = {
            "files": [{"file_type_category": "office_documents", "document_type": "contract", "size": 10}],
            "subfolders": [
                {
                    "files": [{"file_type_category": "images", "document_type": "unknown", "size": 30}],
                    "subfolders": [],
                }
            ],
        }
        stats = scanner.get_statistics(scan)
        assert stats["total_files"] == 2
        assert stats["total_size"] == 40
        assert stats["average_file_size"] == 20
        assert stats["largest_file"] == 30
        assert stats["smallest_file"] == 10

    def test_statistics_empty(self, scanner):
        stats = scanner.get_statistics({})
        assert stats["total_files"] == 0
        assert stats["average_file_size"] == 0

    def test_authenticate_with_missing_credentials(self, scanner, tmp_path):
        scanner.credentials_path = str(tmp_path / "missing.json")
        assert scanner.authenticate() is False

    def test_scan_folder_structure_without_service(self, scanner):
        from app.modules.google_drive.scanner import GOOGLE_DRIVE_AVAILABLE

        if not GOOGLE_DRIVE_AVAILABLE:
            pytest.skip("Google API libraries are not installed")

        result = scanner.scan_folder_structure("folder")
        assert "error" in result

    def test_oauth_scanner_helpers(self):
        from app.modules.google_drive.oauth_scanner import OAuthDriveScanner

        scanner = OAuthDriveScanner("creds.json", "folder")
        assert scanner.categorize_file_type("a.pdf", "") == "office_documents"
        assert scanner.infer_document_type("Смета.xlsx") == "smeta"
        assert scanner.analyze_file(
            {"id": "1", "name": "Паспорт.pdf", "mimeType": "application/pdf"}
        )["document_type"] == "pasport"

    def test_oauth_authenticate_without_token(self, monkeypatch, tmp_path):
        from app.modules.google_drive.oauth_scanner import OAuthDriveScanner

        monkeypatch.setattr(OAuthDriveScanner, "TOKEN_FILE", str(tmp_path / "token.json"))
        scanner = OAuthDriveScanner(str(tmp_path / "missing.json"), "folder")
        assert scanner.authenticate() is False
