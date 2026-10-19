"""Tests for financial ledger integration and Google Drive ledger helpers."""

import json
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


class TestFinancialLedgerIntegration:
    @pytest.fixture()
    def integration(self):
        from app.modules.financial.ledger_integration import FinancialLedgerIntegration

        return FinancialLedgerIntegration(integration_type="mock")

    @pytest.fixture()
    def period(self):
        start = datetime(2024, 1, 1)
        return start, start + timedelta(days=60)

    def test_mock_connection(self, integration):
        assert integration.connect({}) is True

    def test_unknown_integration_connect_fails(self):
        from app.modules.financial.ledger_integration import FinancialLedgerIntegration

        integration = FinancialLedgerIntegration(integration_type="1c")
        assert integration.connect({}) is False

    def test_mock_payments(self, integration, period):
        start, end = period
        payments = integration.get_payments("OBJ-1", start, end)

        assert len(payments) == 2
        assert {p["status"] for p in payments} == {"paid"}
        assert sum(p["amount"] for p in payments) == 800000.0
        assert all(p["object_id"] == "OBJ-1" for p in payments)
        assert payments[0]["payment_id"] == "PAY-OBJ-1-001"

    def test_non_mock_payments_empty(self):
        from app.modules.financial.ledger_integration import FinancialLedgerIntegration

        integration = FinancialLedgerIntegration(integration_type="erp")
        start, end = datetime(2024, 1, 1), datetime(2024, 2, 1)
        assert integration.get_payments("OBJ-1", start, end) == []
        assert integration.get_invoices("OBJ-1", start, end) == []

    def test_mock_invoices(self, integration, period):
        start, end = period
        invoices = integration.get_invoices("OBJ-1", start, end)

        assert len(invoices) == 2
        assert sum(i["amount"] for i in invoices) == 950000.0
        assert {i["status"] for i in invoices} == {"paid", "pending"}

    def test_calculate_burn_rate(self, integration, period):
        start, end = period
        result = integration.calculate_burn_rate("OBJ-1", start, end)

        assert result["total_paid"] == 800000.0
        assert result["days_elapsed"] == 60
        assert result["daily_burn_rate"] == pytest.approx(800000 / 60)
        assert result["payment_count"] == 2
        assert result["start_date"] == start.isoformat()

    def test_calculate_burn_rate_zero_period(self, integration):
        now = datetime(2024, 1, 1)
        result = integration.calculate_burn_rate("OBJ-1", now, now)
        assert result["days_elapsed"] == 0
        assert result["daily_burn_rate"] == 0

    def test_get_cash_flow(self, integration):
        result = integration.get_cash_flow("OBJ-1", months=1)

        assert result["months_analyzed"] == 1
        assert result["total_inflow"] == 800000.0
        assert result["total_outflow"] == 950000.0
        assert result["net_cash_flow"] == -150000.0
        assert len(result["monthly_data"]) == 2

    def test_sync_with_ledger_writes_invoices(self, integration, suffix):
        object_id = f"OBJ-SYNC-{suffix}"
        assert integration.sync_with_ledger(object_id) is True

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT invoice_id, amount, status FROM invoices WHERE object_id = ? ORDER BY invoice_id",
                (object_id,),
            )
            rows = [dict(r) for r in cur.fetchall()]

        assert [r["invoice_id"] for r in rows] == [
            f"PAY-{object_id}-001",
            f"PAY-{object_id}-002",
        ]
        assert sum(r["amount"] for r in rows) == 800000.0

    def test_sync_with_ledger_is_idempotent(self, integration, suffix):
        object_id = f"OBJ-SYNC2-{suffix}"
        assert integration.sync_with_ledger(object_id) is True
        assert integration.sync_with_ledger(object_id) is True

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM invoices WHERE object_id = ?", (object_id,))
            assert cur.fetchone()[0] == 2


class TestFinancialHealthAnalyzer:
    @pytest.fixture()
    def analyzer(self):
        from app.modules.financial.ledger_integration import (
            FinancialHealthAnalyzer,
            FinancialLedgerIntegration,
        )

        return FinancialHealthAnalyzer(FinancialLedgerIntegration())

    @pytest.mark.parametrize(
        "budget,expected",
        [
            (1000000, "high"),
            (800000, "critical"),
            (1200000, "medium"),
            (2000000, "low"),
        ],
    )
    def test_risk_levels(self, analyzer, budget, expected):
        result = analyzer.analyze_cash_gap("OBJ-1", budget)
        assert result["risk_level"] == expected
        assert result["total_paid"] == 800000.0
        assert result["remaining_budget"] == pytest.approx(budget - 800000)

    def test_cash_gap_ratio_with_zero_budget(self, analyzer):
        result = analyzer.analyze_cash_gap("OBJ-1", 0)
        assert result["cash_gap_ratio"] == 0
        assert result["risk_level"] == "low"

    def test_predict_budget_exhaustion(self, analyzer):
        result = analyzer.predict_budget_exhaustion("OBJ-1", 400000)

        assert result is not None
        assert result > datetime.now()
        # 800000 over 30 days -> ~26666/day, 400000 -> ~15 days
        assert 10 <= (result - datetime.now()).days <= 20

    def test_predict_budget_exhaustion_without_payments(self, analyzer, monkeypatch):
        monkeypatch.setattr(
            analyzer.financial_integration,
            "calculate_burn_rate",
            lambda *a, **k: {"daily_burn_rate": 0},
        )
        assert analyzer.predict_budget_exhaustion("OBJ-1", 1000) is None


class TestContractLinker:
    @pytest.fixture()
    def linker(self, monkeypatch):
        import app.modules.google_drive.contract_linker as module

        monkeypatch.setattr(module.ContractLinker, "_load_objects", lambda self: None)
        instance = module.ContractLinker()
        instance.objects_cache = {
            "OBJ-123": {
                "id": 1,
                "object_id": "OBJ-123",
                "object_name": "Судакова 5",
                "customer": "МГТС",
            },
            "OBJ-777": {
                "id": 2,
                "object_id": "OBJ-777",
                "object_name": "Профсоюзная 60",
                "customer": "Моссвет",
            },
        }
        return instance

    @pytest.mark.parametrize(
        "filename,expected",
        [
            ("Договор объект 123.docx", "123"),
            ("OBJ-456 договор.pdf", "456"),
            ("Сектор 7 работы.doc", "7"),
            ("Участок 5 ККС.pdf", "5"),
            ("12345 договор на строительство.docx", "12345"),
            ("Ничего.pdf", None),
        ],
    )
    def test_extract_object_reference(self, linker, filename, expected):
        assert linker.extract_object_reference(filename) == expected

    def test_find_best_match_by_id(self, linker):
        match = linker.find_best_match("объект OBJ-123 договор.pdf")
        assert match["object_id"] == "OBJ-123"

    def test_find_best_match_by_partial_name(self, linker):
        match = linker.find_best_match("объект 123 договор.pdf")
        # "123" is a substring of the object id "OBJ-123"
        assert match["object_id"] == "OBJ-123"

    def test_find_best_match_fuzzy(self, linker):
        match = linker.find_best_match("Договор Судакова 5.pdf")
        assert match["object_id"] == "OBJ-123"

    def test_find_best_match_requires_two_words(self, linker):
        assert linker.find_best_match("Договор Судакова.pdf") is None

    def test_link_contracts(self, linker, suffix):
        contract_id = f"FILE-{suffix}"
        with get_db_connection() as conn:
            conn.cursor().execute("DELETE FROM contract_links WHERE contract_id = ?", (contract_id,))

        result = linker.link_contracts(
            [
                {"id": contract_id, "name": "Договор Судакова 5.pdf"},
                {"id": f"{contract_id}-2", "name": "Неизвестный документ.pdf"},
            ]
        )

        assert result["total_contracts"] == 2
        assert result["linked"] == 1
        assert result["unlinked"] == 1
        assert result["links"][0]["object_id"] == "OBJ-123"

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT contract_name, object_id, confidence FROM contract_links WHERE contract_id = ?",
                (contract_id,),
            )
            row = dict(cur.fetchone())
        assert row["object_id"] == "OBJ-123"
        assert row["confidence"] == "medium"

    def test_link_contracts_is_idempotent(self, linker, suffix):
        contract_id = f"FILE-IDEM-{suffix}"
        contracts = [{"id": contract_id, "name": "Договор объект 777.pdf"}]

        linker.link_contracts(contracts)
        linker.link_contracts(contracts)

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM contract_links WHERE contract_id = ?", (contract_id,))
            assert cur.fetchone()[0] == 1

    def test_link_contracts_high_confidence(self, linker, suffix):
        contract_id = f"FILE-HIGH-{suffix}"
        linker.link_contracts([{"id": contract_id, "name": "Договор объект 777.pdf"}])

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT confidence FROM contract_links WHERE contract_id = ?", (contract_id,)
            )
            assert cur.fetchone()["confidence"] == "high"

    def test_get_unlinked_contracts(self, linker):
        assert linker.get_unlinked_contracts() == []

    def test_create_contract_links_table_is_idempotent(self):
        from app.modules.google_drive.contract_linker import create_contract_links_table

        create_contract_links_table()
        create_contract_links_table()

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='contract_links'"
            )
            assert cur.fetchone() is not None


class TestProjectLedgerManager:
    @pytest.fixture()
    def manager(self, tmp_path):
        from app.modules.google_drive.project_ledger_manager import ProjectLedgerManager

        return ProjectLedgerManager(tmp_path)

    def test_init_creates_index(self, manager):
        assert manager.ledgers_index == {}
        assert manager.ledgers_index_file.exists() is False

    def test_create_ledger_name(self, manager):
        assert manager.create_ledger_name("Судакова 5", "МГТС") == "Судакова 5 - МГТС"
        assert manager.create_ledger_name("  Судакова 5  ") == "Судакова 5"

    def test_sanitize_dir_name(self, manager):
        assert manager._sanitize_dir_name('a/b:c*?') == "a_b_c_"

    def test_infer_customer_from_path(self, manager):
        assert manager.infer_customer_from_path("5_Стройка/МГТС/Судакова 5") == "МГТС"
        assert manager.infer_customer_from_path("5_Стройка/Неизвестно") is None

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("Москва, Судакова 5", True),
            ("Судакова 5", True),
            ("Маршала Жукова 25/1 (ГК ПИК)", True),
            ("Профсоюзная 60к1", True),
            ("Сергиев Посад", True),
            ("РД 2024", False),
            ("Этап 1", False),
            ("ВОЛС объект", False),
            ("20230602", False),
            ("1 Замечания", False),
            ("ab", False),
        ],
    )
    def test_is_construction_object(self, manager, name, expected):
        assert manager._is_construction_object(name) is expected

    def test_detect_object_folders_old_format(self, manager):
        result = manager.detect_object_folders(
            {
                "folders": {
                    "o1": {"name": "Москва, Судакова 5", "path": "5_Стройка/Москва, Судакова 5"},
                    "o2": {"name": "Этап 1", "path": "5_Стройка/Этап 1"},
                }
            }
        )
        assert [item["folder_id"] for item in result] == ["o1"]

    def test_detect_object_folders_tree_format(self, manager):
        scan = {
            "folder_structure": {
                "name": "5_Стройка",
                "folder_id": "root",
                "subfolders": [
                    {
                        "name": "Москва. Стройка",
                        "folder_id": "c1",
                        "subfolders": [
                            {"name": "Москва, Судакова 5", "folder_id": "o1", "subfolders": []},
                            {"name": "Этап 1", "folder_id": "o2", "subfolders": []},
                        ],
                    },
                    {
                        "name": "МГТС",
                        "folder_id": "c2",
                        "subfolders": [
                            {"name": "Профсоюзная 60", "folder_id": "o3", "subfolders": []},
                        ],
                    },
                ],
            }
        }
        result = manager.detect_object_folders(scan)

        by_id = {item["folder_id"]: item for item in result}
        assert set(by_id) == {"o1", "o3"}
        assert by_id["o3"]["customer"] == "МГТС"
        assert by_id["o3"]["ledger_name"] == "Профсоюзная 60 - МГТС"
        assert by_id["o1"]["customer"] is None

    def test_detect_object_folders_skips_system_folders(self, manager):
        scan = {
            "folder_structure": {
                "name": "5_Стройка",
                "folder_id": "root",
                "subfolders": [
                    {"name": "Архив", "folder_id": "a", "subfolders": []},
                    {"name": "!_Сканы", "folder_id": "b", "subfolders": []},
                ],
            }
        }
        assert manager.detect_object_folders(scan) == []

    def test_create_object_ledger(self, manager, tmp_path):
        from app.modules.google_drive.project_ledger_manager import ObjectMetadata

        metadata = ObjectMetadata(
            ledger_name="Судакова 5 - МГТС",
            address="Москва, Судакова 5",
            customer="МГТС",
            google_drive_folder_id="folder-1",
            telegram_chat_id=123,
        )
        path = manager.create_object_ledger(metadata)

        assert Path(path).is_dir()
        assert (Path(path) / "metadata.json").exists()
        assert manager.get_ledger_by_name("Судакова 5 - МГТС")["metadata"]["customer"] == "МГТС"

        # index survives a restart
        from app.modules.google_drive.project_ledger_manager import ProjectLedgerManager

        reloaded = ProjectLedgerManager(tmp_path)
        assert "Судакова 5 - МГТС" in reloaded.get_all_ledgers()

    def test_object_metadata_defaults(self):
        from app.modules.google_drive.project_ledger_manager import ObjectMetadata

        metadata = ObjectMetadata(ledger_name="X", address="Y", customer="Z")
        assert metadata.city == "Москва"
        assert metadata.created_at
        assert metadata.last_synced is None

    def test_update_last_synced(self, manager):
        from app.modules.google_drive.project_ledger_manager import ObjectMetadata

        manager.create_object_ledger(ObjectMetadata("X", "Y", "Z"))
        assert manager.get_ledger_by_name("X")["metadata"]["last_synced"] is None

        manager.update_last_synced("X")
        assert manager.get_ledger_by_name("X")["last_synced"]

    def test_update_last_synced_unknown_ledger(self, manager):
        manager.update_last_synced("missing")
        assert manager.get_all_ledgers() == {}

    def test_add_document_reference(self, manager, tmp_path):
        from app.modules.google_drive.project_ledger_manager import ObjectMetadata

        path = manager.create_object_ledger(ObjectMetadata("X", "Y", "Z"))
        manager.add_document_reference(
            "X",
            {
                "source": "google_drive",
                "source_id": "file-1",
                "source_url": "https://drive.google.com/file/d/file-1",
                "file_name": "contract.pdf",
                "added_at": "2026-01-01T00:00:00",
            },
        )

        reference = json.loads((Path(path) / "documents" / "file-1.json").read_text(encoding="utf-8"))
        assert reference["file_name"] == "contract.pdf"

    def test_add_document_reference_unknown_ledger(self, manager):
        manager.add_document_reference("missing", {"source_id": "1", "file_name": "a"})
        assert manager.get_all_ledgers() == {}


class TestKnowledgeSummarizer:
    @pytest.fixture()
    def summarizer(self, monkeypatch, tmp_path, suffix):
        import app.modules.google_drive.knowledge_summarizer as module

        object_id = f"OBJ-KS-{suffix}"
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO objects
                   (object_name, object_id, customer, customer_company, contract_date,
                    contract_amount, contract_number, has_proposal, proposal_date,
                    proposal_amount, converted_to_contract)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, 1)""",
                (
                    "Тестовый объект",
                    object_id,
                    "МГТС",
                    "ПАО МГТС",
                    "2024-01-15",
                    1000000.0,
                    "123/2024",
                    "2024-01-01",
                    900000.0,
                ),
            )
            cur.execute(
                "INSERT INTO contract_links (contract_id, contract_name, object_id, confidence) VALUES (?,?,?,?)",
                (f"c-{suffix}", "Договор.pdf", object_id, "high"),
            )
            cur.execute(
                "INSERT INTO object_events (object_id, event_type, event_date, description) VALUES (?,?,?,?)",
                (object_id, "contract_signed", "2024-01-15", "Договор подписан"),
            )
            cur.execute(
                "INSERT INTO object_events (object_id, event_type, event_date, description) VALUES (?,?,?,?)",
                (object_id, "comment", "2024-01-16", "Комментарий"),
            )
            cur.execute(
                "INSERT INTO invoices (invoice_id, object_id, amount, date, status) VALUES (?,?,?,?,?)",
                (f"i-{suffix}", object_id, 250000.0, "2024-02-01", "paid"),
            )

        instance = module.KnowledgeSummarizer.__new__(module.KnowledgeSummarizer)
        instance.document_ingestor = SimpleNamespace(
            search_similar_documents=lambda **kwargs: [
                {
                    "metadata": {
                        "source_file": "docs/a.pdf",
                        "file_name": "a.pdf",
                        "document_type": "contract",
                        "chunk_total": 3,
                        "ingested_at": "2024-01-01",
                    }
                }
            ]
        )
        instance.contract_linker = None
        return instance, object_id

    def test_generate_object_summary(self, summarizer):
        instance, object_id = summarizer
        summary = instance.generate_object_summary(object_id)

        assert summary["object_id"] == object_id
        assert summary["basic_info"]["object_name"] == "Тестовый объект"
        assert summary["basic_info"]["contract_amount"] == 1000000.0
        assert summary["basic_info"]["has_proposal"] is True
        assert len(summary["contracts"]) == 1
        assert summary["contracts"][0]["contract_name"] == "Договор.pdf"
        assert summary["documents"][0]["file_name"] == "a.pdf"
        assert summary["financials"]["invoice_count"] == 1
        assert summary["financials"]["invoice_total"] == 250000.0
        assert summary["financials"]["remaining_budget"] == 750000.0
        assert len(summary["timeline"]) == 2
        assert summary["key_events"] == ["2024-01-15: Договор подписан"]

    def test_generate_text_summary(self, summarizer):
        instance, object_id = summarizer
        text = instance.generate_text_summary(object_id)

        assert "Объект: Тестовый объект" in text
        assert "Заказчик: МГТС" in text
        assert "Связанные контракты: 1" in text
        assert "Договор.pdf" in text
        assert "Оплачено: 250,000.00 руб." in text
        assert "Остаток: 750,000.00 руб." in text
        assert "Договор подписан" in text

    def test_summary_for_unknown_object(self, summarizer):
        instance, _ = summarizer
        summary = instance.generate_object_summary("OBJ-MISSING")
        assert summary["basic_info"] == {}
        assert summary["contracts"] == []
        assert summary["timeline"] == []
        assert summary["financials"]["contract_amount"] == 0
        assert summary["financials"]["invoice_total"] == 0

    def test_generate_all_summaries(self, summarizer):
        instance, object_id = summarizer
        summaries = instance.generate_all_summaries()
        assert object_id in summaries
        assert summaries[object_id]["object_id"] == object_id

    def test_get_documents_handles_chroma_errors(self, summarizer, monkeypatch):
        instance, object_id = summarizer

        def boom(**kwargs):
            raise RuntimeError("chroma down")

        instance.document_ingestor = SimpleNamespace(search_similar_documents=boom)
        assert instance._get_documents(object_id) == []


class TestDocumentProcessor:
    class FakeDownloader:
        def __init__(self, result=None):
            self.result = result or {"success": False, "error": "no"}

        def download_file(self, file_id, output_path, file_name):
            return self.result

    @pytest.fixture()
    def processor(self, tmp_path):
        from app.modules.google_drive.document_processor import DocumentProcessor

        return DocumentProcessor(str(tmp_path / "creds.json"), tmp_path / "downloads")

    def test_downloader_not_authenticated(self, tmp_path, monkeypatch):
        from app.modules.google_drive.document_processor import GoogleDriveDownloader

        monkeypatch.setattr(
            GoogleDriveDownloader, "TOKEN_FILE", str(tmp_path / "token.json")
        )
        downloader = GoogleDriveDownloader(str(tmp_path / "creds.json"))
        assert downloader.authenticate() is False
        assert downloader.download_file("1", tmp_path / "a.txt", "a.txt") == {
            "success": False,
            "error": "Not authenticated",
        }

    def test_process_file_download_failure(self, processor):
        processor.downloader = self.FakeDownloader()
        result = processor.process_file("id1", "a.txt")

        assert result["success"] is False
        assert result["error"] == "Download failed: no"

    def test_process_file_success(self, processor, tmp_path):
        downloaded = tmp_path / "downloads" / "a.txt"
        downloaded.parent.mkdir(parents=True, exist_ok=True)
        downloaded.write_text("Текст", encoding="utf-8")

        processor.downloader = self.FakeDownloader(
            {
                "success": True,
                "file_path": str(downloaded),
                "file_name": "a.txt",
                "exported": False,
            }
        )
        result = processor.process_file("id1", "a.txt", subfolder="sub")

        assert result["success"] is True
        assert result["actual_file_name"] == "a.txt"
        assert result["parse_result"]["text"] == "Текст"

    def test_process_files_batch(self, processor, tmp_path):
        downloaded = tmp_path / "downloads" / "a.txt"
        downloaded.parent.mkdir(parents=True, exist_ok=True)
        downloaded.write_text("Текст", encoding="utf-8")

        processor.downloader = self.FakeDownloader(
            {"success": True, "file_path": str(downloaded), "file_name": "a.txt"}
        )
        results = processor.process_files_batch([{"id": "1", "name": "a.txt"}])
        assert len(results) == 1
        assert results[0]["success"] is True

    def test_process_scan_result(self, processor, tmp_path, monkeypatch):
        scan = {
            "folder_structure": {
                "files": [
                    {"id": "1", "name": "a.txt", "path": "root/a.txt"},
                    {"id": "2", "name": "drawing.dwg", "path": "root/drawing.dwg"},
                ],
                "subfolders": [
                    {"files": [{"id": "3", "name": "b.txt", "path": "root/sub/b.txt"}], "subfolders": []}
                ],
            }
        }
        scan_file = tmp_path / "scan.json"
        scan_file.write_text(json.dumps(scan), encoding="utf-8")

        downloaded = tmp_path / "downloads" / "a.txt"
        downloaded.parent.mkdir(parents=True, exist_ok=True)
        downloaded.write_text("Текст", encoding="utf-8")

        processor.downloader = self.FakeDownloader(
            {"success": True, "file_path": str(downloaded), "file_name": "a.txt"}
        )

        result = processor.process_scan_result(str(scan_file), max_files=2, skip_dwg=True)
        assert result["total_files"] == 2
        assert result["successful"] == 2
        assert result["failed"] == 0
        assert all(r["scan_info"]["name"] != "drawing.dwg" for r in result["results"])

    def test_process_scan_result_includes_dwg_when_not_skipped(self, processor, tmp_path):
        scan = {
            "folder_structure": {
                "files": [{"id": "2", "name": "drawing.dwg", "path": "root/drawing.dwg"}],
                "subfolders": [],
            }
        }
        scan_file = tmp_path / "scan.json"
        scan_file.write_text(json.dumps(scan), encoding="utf-8")

        processor.downloader = self.FakeDownloader()
        result = processor.process_scan_result(str(scan_file), skip_dwg=False)
        assert result["total_files"] == 1
        assert result["failed"] == 1

    def test_export_file_without_service(self, processor, tmp_path):
        from app.modules.google_drive.document_processor import GoogleDriveDownloader

        downloader = GoogleDriveDownloader(str(tmp_path / "creds.json"))
        result = downloader.export_file(
            "1", tmp_path / "a.docx", "a.docx", "application/vnd.google-apps.document"
        )
        assert result["success"] is False
