# Architectural Sync Report

**Date**: 13 сентября 2026  
**Updated**: 19 октября 2026 — статусы синхронизированы с фактическим состоянием  
**Purpose**: Resolve critical architectural contradictions and introduce Chronological Project Ledger feature

---

## 🎯 Summary of Changes

### 1. VRAM & Model Execution Contradiction ✅ RESOLVED

**Problem**: References to single unified daytime/nighttime model causing VRAM OOM on RTX 5060.

**Solution**: Explicit multi-model pipeline implementation:
- **DAYTIME**: qwen2.5:14b-instruct (Primary Chat)
- **NIGHTTIME**: qwen2.5-vl:7b (Vision/OCR monopoly slot)
- **Rationale**: Day/Night switching prevents VRAM thrashing on single-GPU systems

**Files Updated**:
- `architecture.md` - Updated Deployment Environment section
- `architecture.md` - Updated VRAM Management section with explicit multi-model configuration
- `Todo.md` - Marked resolution as COMPLETED

---

### 2. AnythingLLM Deprecation ✅ COMPLETED

**Problem**: External AnythingLLM dependency when native Hybrid RAG handles construction queries.

**Solution**: Mark AnythingLLM as deprecated. Native Hybrid RAG (SQLite + ChromaDB via bge-m3 embeddings) handles exact construction queries, tables, and document structures without external web-service overhead.

**Files Updated**:
- `architecture.md` - Marked AnythingLLM as ~~DEPRECATED~~
- `Todo.md` - Marked as COMPLETED with rationale

---

### 3. Chronological Project Ledger ("Project Diary") ✅ ADDED

**Concept**: A chronological state-machine ledger that handles document versions, technical specification (ТУ) amendments, and chat updates sequentially.

**Database Schema**:
```sql
CREATE TABLE project_ledger (
    ledger_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    event_timestamp TIMESTAMP NOT NULL, -- Date the document/fact actually became true
    discovered_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    entity_type TEXT NOT NULL, -- 'document', 'chat_fact', 'financial', 'material'
    entity_id TEXT NOT NULL,
    revision_index INTEGER DEFAULT 0, -- 0 for original, 1+ for updates/corrections
    overrides_ledger_id INTEGER REFERENCES project_ledger(ledger_id), -- Pointer to superseded data
    summary_delta TEXT NOT NULL, -- "Amended capacity from 50kW to 75kW"
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);
CREATE INDEX idx_ledger_chronology ON project_ledger (project_id, event_timestamp ASC);
```

**Files Updated**:
- `architecture.md` - Added project_ledger table schema under Data Layer Architecture
- `architecture.md` - Added Ledger concept explanation
- `ai.md` - Added LedgerEventSchema with modern Pydantic v2 syntax
- `Todo.md` - Added ЭТАП 7.10 (Chronological State Replay Engine) - ✅ COMPLETED
- `Todo.md` - Added ЭТАП 7.11 (Implicit Override Detection) - ✅ COMPLETED

---

### 4. Pydantic Modernization ✅ COMPLETED

**Problem**: Inconsistent Pydantic v2 syntax (old class-based Config vs modern ConfigDict).

**Solution**: Migrate all schemas to modern `model_config = ConfigDict(...)` syntax.

**Files Updated**:
- `ai.md` - Added ConfigDict import to all schema sections
- `ai.md` - Added LedgerEventSchema with modern syntax
- `ai.md` - Replaced all `class Config:` with `model_config = ConfigDict(` (13 instances)
- `Todo.md` - Marked 6.8 as ✅ COMPLETED
- `Todo.md` - Added 6.11 (Modernize Pydantic Syntax) - ✅ COMPLETED

---

### 5. Google Drive Sequential Processing Policy ✅ ADDED

**Requirements**:
1. **Sorting Before Ingestion**: Files must be parsed and indexed according to creation/modification metadata
2. **Parent-Child Mapping**: Revision keywords trigger overrides_ledger_id linkage
3. **Chat Priority Handling**: Authoritative chat facts supersede formal documents

**Files Updated**:
- `docs/rfc_google_drive_analysis.md` - Added Section 4.5 with Sequential Document Processing Policy
- `docs/rfc_google_drive_analysis.md` - Added subsections 4.5.1, 4.5.2, 4.5.3

---

## 📋 Updated Files Summary

### 1. `C:\mia\architecture.md`
- ✅ Fixed VRAM contradiction (multi-model pipeline)
- ✅ Deprecated AnythingLLM
- ✅ Added project_ledger table schema
- ✅ Added Ledger concept explanation

### 2. `C:\mia\Todo.md`
- ✅ Updated ЭТАП 6.6 (AnythingLLM deprecated)
- ✅ Updated ЭТАП 6.7 (documentation sync)
- ✅ Updated ЭТАП 6.8 (Pydantic modernization)
- ✅ Added ЭТАП 6.10 (Safe Tool Generation Layer)
- ✅ Added ЭТАП 6.11 (Modernize Pydantic Syntax)
- ✅ Updated ЭТАП 7.10 (Chronological State Replay Engine)
- ✅ Updated ЭТАП 7.11 (Implicit Override Detection)

### 3. `C:\mia\ai.md`
- ✅ Added ConfigDict import
- ✅ Added LedgerEventSchema with modern syntax
- ✅ Converted 13 instances of `class Config:` to `model_config = ConfigDict(`

### 4. `C:\mia\docs\rfc_google_drive_analysis.md`
- ✅ Added Section 4.5 (Sequential Document Processing Policy)
- ✅ Added subsections for chronological ingestion, revision mapping, chat priority

---

## 🚀 Next Steps

### Completed (since 2026-09-13):
1. ✅ **Test project_ledger table creation** — покрыто тестами (`tests/test_state_replay_overrides.py`)
2. ✅ **Complete Pydantic modernization** — class-based `Config` отсутствует, все схемы на `ConfigDict`
3. ✅ **Implement Safe Tool Generation Layer** — `app/core/safe_tool_layer.py` + 31 тест
4. ✅ **Chronological State Replay Engine** — `app/modules/rag/state_replay.py` (7.14/9.6)
5. ✅ **Implicit Override Detection** — `app/modules/google_drive/override_detector.py` (7.15/9.7)

### Remaining (Deferred):
6. ⏸️ **PostgreSQL Migration (9.11)** — требует внешнего setup

---

## ✅ Architectural Contradictions Resolved

1. ✅ VRAM & Model Execution Contradiction - RESOLVED
2. ✅ AnythingLLM Dependency - DEPRECATED
3. ✅ Chronological State Tracking - LEDGER ADDED
4. ✅ Pydantic Syntax Inconsistency - COMPLETED
5. ✅ Sequential Document Processing - POLICY ADDED

---

**Status**: Architectural sync complete. All immediate tasks completed; only PostgreSQL migration (9.11) remains deferred.