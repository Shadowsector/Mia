"""Tests for Chronological State Replay Engine (7.14) and Implicit Override Detection (7.15)."""

import pytest

from app.modules.rag.state_replay import StateReplayEngine, CHROMADB_AVAILABLE
from app.modules.google_drive.override_detector import (
    OverrideDetector,
    DocumentOverrideManager,
    PANDAS_AVAILABLE,
)
from app.modules.storage.database import initialize_database, get_db_connection


@pytest.fixture(scope="module")
def replay_engine(tmp_path_factory):
    if not CHROMADB_AVAILABLE:
        pytest.skip("chromadb not installed")
    persist = tmp_path_factory.mktemp("chroma_replay")
    return StateReplayEngine(persist_directory=str(persist))


@pytest.fixture(scope="module")
def detector():
    return OverrideDetector()


@pytest.fixture(scope="module", autouse=True)
def db():
    initialize_database()
    with get_db_connection() as conn:
        yield conn


class TestStateReplayEngine:
    def test_register_and_get_actual_version(self, replay_engine):
        replay_engine.register_document_version(
            document_id="DOC-R1",
            document_name="Смета.xlsx",
            revision_index=0,
            object_id="OBJ-R1",
        )
        replay_engine.register_document_version(
            document_id="DOC-R1",
            document_name="Смета.xlsx",
            revision_index=1,
            object_id="OBJ-R1",
        )
        actual = replay_engine.get_actual_version("DOC-R1")
        assert actual is not None
        assert actual["revision_index"] == 1
        assert actual["status"] == "actual"

    def test_old_versions_marked_obsolete(self, replay_engine):
        history = replay_engine.get_version_history("DOC-R1")
        statuses = {v["revision_index"]: v["status"] for v in history}
        assert statuses[0] == "obsolete"
        assert statuses[1] == "actual"

    def test_replay_state_up_to_date(self, replay_engine):
        # Register an old revision with an old timestamp, then replay to an
        # intermediate date: the older revision must win at that point.
        from datetime import datetime
        import json

        replay_engine.register_document_version(
            document_id="DOC-R2",
            document_name="Договор.docx",
            revision_index=0,
            object_id="OBJ-R2",
            metadata={"created_at": "2026-01-01T00:00:00"},
        )
        replay_engine.collection.update(
            ids=["DOC-R2_rev_0"],
            metadatas=[{
                "version_id": "DOC-R2_rev_0",
                "document_id": "DOC-R2",
                "document_name": "Договор.docx",
                "revision_index": 0,
                "object_id": "OBJ-R2",
                "status": "actual",
                "created_at": "2026-01-01T00:00:00",
                "metadata": json.dumps({}),
            }],
        )
        state = replay_engine.replay_state("OBJ-R2", datetime(2026, 6, 1))
        assert "DOC-R2" in state["state"]
        assert state["state"]["DOC-R2"]["revision_index"] == 0

    def test_replay_empty_object(self, replay_engine):
        from datetime import datetime

        state = replay_engine.replay_state("OBJ-NOBODY", datetime(2026, 6, 1))
        assert state["state"] == {}
        assert state.get("message") == "No versions found"

    def test_version_history_sorted_desc(self, replay_engine):
        history = replay_engine.get_version_history("DOC-R1")
        revs = [v["revision_index"] for v in history]
        assert revs == sorted(revs, reverse=True)


class FakeCollection:
    """Minimal ChromaDB collection stand-in for ChunkVersionManager tests."""

    def __init__(self):
        self.store = {}

    def add(self, ids, documents, metadatas):
        for i, doc_id in enumerate(ids):
            self.store[doc_id] = {"document": doc_id, "metadata": metadatas[i], "text": documents[i]}

    def get(self, where=None):
        ids, docs, metas = [], [], []
        for chunk_id, rec in self.store.items():
            meta = rec["metadata"]
            if self._match(meta, where):
                ids.append(chunk_id)
                docs.append(rec["text"])
                metas.append(meta)
        return {"ids": ids, "documents": docs, "metadatas": metas}

    def update(self, ids, metadatas):
        for i, chunk_id in enumerate(ids):
            if chunk_id in self.store:
                self.store[chunk_id]["metadata"] = metadatas[i]

    def query(self, query_texts, n_results, where):
        matches = self.get(where)
        return {
            "documents": [[self.store[i]["text"] for i in matches["ids"][:n_results]]],
            "metadatas": [[self.store[i]["metadata"] for i in matches["ids"][:n_results]]],
            "distances": [[0.0] * min(n_results, len(matches["ids"]))],
        }

    @staticmethod
    def _match(meta, where):
        if not where:
            return True
        if "$and" in where:
            return all(FakeCollection._match(meta, sub) for sub in where["$and"])
        for key, cond in where.items():
            val = meta.get(key)
            if isinstance(cond, dict):
                if "$lt" in cond and not (val is not None and val < cond["$lt"]):
                    return False
            elif val != cond:
                return False
        return True


class FakeChromaManager:
    def __init__(self):
        self.collection = FakeCollection()


class TestChunkVersionManager:
    @pytest.fixture()
    def manager(self, replay_engine):
        from app.modules.rag.state_replay import ChunkVersionManager

        return ChunkVersionManager(FakeChromaManager(), replay_engine)

    def test_add_and_query_actual_chunks(self, manager):
        ok = manager.add_versioned_chunks(
            document_id="DOC-C1",
            document_name="Смета.xlsx",
            revision_index=0,
            chunks=[{"text": "ИТОГО 100 руб", "metadata": {"object_id": "OBJ-C1"}}],
            object_id="OBJ-C1",
        )
        assert ok

        ok = manager.add_versioned_chunks(
            document_id="DOC-C1",
            document_name="Смета.xlsx",
            revision_index=1,
            chunks=[{"text": "ИТОГО 120 руб", "metadata": {"object_id": "OBJ-C1"}}],
            object_id="OBJ-C1",
        )
        assert ok

        results = manager.query_actual_chunks("ИТОГО", object_id="OBJ-C1")
        texts = [r["text"] for r in results]
        # Only the latest revision may be returned
        assert "ИТОГО 120 руб" in texts
        assert "ИТОГО 100 руб" not in texts

    def test_mark_chunks_obsolete(self, manager):
        manager.add_versioned_chunks(
            document_id="DOC-C2",
            document_name="Договор.docx",
            revision_index=0,
            chunks=[{"text": "старый текст", "metadata": {}}],
        )
        manager.mark_chunks_obsolete("DOC-C2", revision_index=1)
        results = manager.query_actual_chunks("старый")
        assert results == []


class TestOverrideDetector:
    def test_detect_override_by_name(self, detector):
        assert detector.detect_override_candidate("Смета_правленная_последняя.xlsx")
        assert detector.detect_override_candidate("смета_ИТОГ.xlsx")
        assert detector.detect_override_candidate("Project_final_v2.dwg")

    def test_regular_file_not_override(self, detector):
        assert not detector.detect_override_candidate("Смета_исходная.xlsx")
        assert not detector.detect_override_candidate("Договор_№12.docx")

    def test_base_name_extraction(self, detector):
        base = detector.detect_override_by_name_pattern("Смета_итог.xlsx")
        assert base is not None
        assert "итог" not in base.lower()

    def test_base_name_none_for_regular(self, detector):
        assert detector.detect_override_by_name_pattern("Договор_№12.docx") is None

    @pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not installed")
    def test_structure_hash_stable(self, detector, tmp_path):
        f = tmp_path / "a.xlsx"
        import pandas as pd

        pd.DataFrame({"col1": [1, 2], "col2": ["a", "b"]}).to_excel(f, index=False)
        h1 = detector.extract_structure_hash(str(f))
        h2 = detector.extract_structure_hash(str(f))
        assert h1 is not None and h1 == h2
        assert detector.calculate_structure_similarity(h1, h2) == 1.0

    @pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not installed")
    def test_compare_excel_structures(self, detector, tmp_path):
        import pandas as pd

        f1 = tmp_path / "v1.xlsx"
        f2 = tmp_path / "v2.xlsx"
        pd.DataFrame({"a": [1], "b": [2]}).to_excel(f1, index=False)
        pd.DataFrame({"a": [1], "b": [2], "c": [3]}).to_excel(f2, index=False)
        result = detector.compare_excel_structures(str(f1), str(f2))
        assert "error" not in result
        sheet = next(iter(result["sheet_comparisons"].values()))
        assert 0 < sheet["column_similarity"] < 1

    def test_nonexistent_file_returns_none(self, detector):
        assert detector.extract_structure_hash("C:\\mia\\no_such_file.xlsx") is None

    @pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not installed")
    def test_find_potential_overrides_exact_match(self, detector, tmp_path):
        import pandas as pd

        f1 = tmp_path / "Смета.xlsx"
        f2 = tmp_path / "Смета_правленная.xlsx"
        pd.DataFrame({"x": [1, 2, 3]}).to_excel(f1, index=False)
        pd.DataFrame({"x": [1, 2, 3]}).to_excel(f2, index=False)
        found = detector.find_potential_overrides(str(f2), [str(f1)])
        assert len(found) == 1
        assert found[0]["similarity"] == 1.0


class TestDocumentOverrideManager:
    @pytest.fixture()
    def manager(self, db):
        # document_links lives in document_linker — ensure it exists
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS document_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL,
                document_name TEXT NOT NULL,
                object_id TEXT NOT NULL,
                link_type TEXT,
                confidence REAL DEFAULT 0.5,
                citation_text TEXT,
                citation_page INTEGER,
                citation_bbox TEXT,
                linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verified_by TEXT,
                verification_status TEXT DEFAULT 'AUTO_VERIFIED',
                status TEXT DEFAULT 'active',
                deprecated_by TEXT
            )
            """
        )
        db.commit()
        return DocumentOverrideManager()

    def test_register_and_get_chain(self, manager, db):
        override_id = manager.register_override(
            base_document_id="BASE-1",
            override_document_id="OVR-1",
            override_version=1,
            similarity_score=0.95,
            detection_method="structure_hash",
        )
        assert override_id > 0
        chain = manager.get_override_chain("BASE-1")
        assert len(chain) >= 1
        assert chain[0]["override_document_id"] == "OVR-1"

    def test_mark_document_deprecated(self, manager, db):
        db.execute(
            "INSERT INTO document_links (document_id, document_name, object_id) "
            "VALUES (?, ?, ?)",
            ("DOC-DEP", "старый.docx", "OBJ-X"),
        )
        db.commit()
        ok = manager.mark_document_deprecated("DOC-DEP", "DOC-NEW")
        assert ok
        row = db.execute(
            "SELECT status, deprecated_by FROM document_links WHERE document_id = ?",
            ("DOC-DEP",),
        ).fetchone()
        assert row["status"] == "deprecated"
        assert row["deprecated_by"] == "DOC-NEW"
