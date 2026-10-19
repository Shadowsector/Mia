"""Tests for ImprovedDocumentClassifier (Google Drive classification)."""

import json

import pytest

from app.modules.google_drive.document_classifier import ImprovedDocumentClassifier


@pytest.fixture()
def clf():
    return ImprovedDocumentClassifier()


class TestSeparatorNormalization:
    def test_underscore_is_word_boundary(self, clf):
        # 'паспорт_трассы' is a route passport (specific passport subtype)
        assert clf.classify("паспорт_трассы.pdf") == "pasport_svyazi"
        assert clf.classify("паспорт_4.pdf") == "passport"

    def test_dash_separator(self, clf):
        assert clf.classify("РД-01_план.docx") == "rd"

    def test_bracketed_number(self, clf):
        assert clf.classify("паспорт (4).pdf") == "passport"

    def test_technical_passport_variants(self, clf):
        for name in (
            "Тех.паспорт Ереванская ул., д. 7.pdf",
            "ТЕХПАСПОРТ д 12 корп 1.pdf",
        ):
            assert clf.classify(name) == "passport", name


class TestFrequentPatterns:
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("Титул_проекта.pdf", "titul"),
            ("Обложка_документа.docx", "oblozhka"),
            ("Содержание.docx", "soderzhanie"),
            ("Ведомость_материалов.xlsx", "vedomost"),
            ("Профиль_трассы.dwg", "profil"),
            ("Вынос_точек.xlsx", "vynos"),
            ("Сборочный_чертеж.dwg", "sborka"),
            ("Узел_1.dwg", "uzel"),
            ("Сертификат_соответствия.pdf", "sertifikat"),
            ("Выписка_ЕГРН.pdf", "vypiska"),
            ("Журнал_производства_работ.docx", "zhurnal"),
            ("Акт_сверки.docx", "akt_sverki"),
            ("Доверенность.pdf", "doverennost"),
            ("Смета_ИТОГ.xlsx", "smeta"),
            ("Разработка_пояснительная.docx", "razrabotka"),
            ("Грунта_веерная_диаграмма.pdf", "grunt"),
            ("Труба_сталь_108.docx", "truba"),
            ("Реестр_документов.xlsx", "reestr"),
        ],
    )
    def test_known_documents(self, clf, name, expected):
        assert clf.classify(name) == expected

    def test_russian_and_english_passport(self, clf):
        assert clf.classify("passport_2024.pdf") == "passport"
        assert clf.classify("проект_reconstruction.docx") == "project"


class TestCadExtensions:
    def test_drawing(self, clf):
        assert clf.classify("output[1-3].dwg") == "cad_drawing"

    def test_service_files(self, clf):
        for name in ("plot.log", "backup.bak", "font.shx", "style.ctb"):
            assert clf.classify(name) == "cad_service", name

    def test_meaningful_dwg_name_wins_over_extension(self, clf):
        assert clf.classify("план_этажера_1.dwg") == "plan"

    def test_image_fallback(self, clf):
        assert clf.classify("photo_2024.jpg") == "image"

    def test_archive_fallback(self, clf):
        assert clf.classify("backup_scans.zip") == "archive"

    def test_unknown_fallback(self, clf):
        assert clf.classify("asdkjhqwe") == "unknown"


class TestBatch:
    def test_classify_batch_counts(self, clf):
        stats = clf.classify_batch(
            ["паспорт.pdf", "паспорт_2.docx", "random.xyz"]
        )
        assert stats["passport"] == 2
        assert stats["unknown"] == 1
        assert sum(stats.values()) == 3


class TestRealScanData:
    """Smoke test against real reclassified scan (if present)."""

    def test_unknown_ratio_below_threshold(self, clf):
        try:
            with open(
                "google_drive_scan_result_reclassified.json", encoding="utf-8"
            ) as f:
                data = json.load(f)
        except FileNotFoundError:
            pytest.skip("scan result not available")

        names = []

        def walk(node):
            for fl in node.get("files", []) or []:
                names.append(fl.get("name", ""))
            for sub in node.get("subfolders", []) or []:
                walk(sub)
            if "folder_structure" in node:
                walk(node["folder_structure"])

        walk(data)
        if not names:
            pytest.skip("no files in scan")

        stats = clf.classify_batch(names)
        unknown_ratio = stats.get("unknown", 0) / len(names)
        # Was 70.7% before classifier improvements; now <25%
        assert unknown_ratio < 0.25, f"unknown ratio {unknown_ratio:.1%}"
