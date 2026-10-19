# Mia PM OS - Architecture Documentation

## Documentation Standards

### RFC Status Marking
When implementing features from RFC documents, maintain status tracking:
- ✅ **COMPLETED**: Feature fully implemented and tested
- 🔄 **IN PROGRESS**: Currently being implemented
- ⏸️ **DEFERRED**: Planned but not started
- ❌ **CONFLICTS**: Conflicts with other RFCs or current architecture
- 🚫 **CANCELLED**: No longer relevant

Example:
```markdown
### Feature X
- RFC: mia_architecture_rfc.md, Section 3.2
- Status: ✅ COMPLETED
- Implementation: app/modules/feature_x.py
- Notes: Added support for Google Drive integration
```

## System Overview

Mia PM OS is a local, privacy-preserving AI Construction Project Management System designed for utility/civil-construction companies. It manages underground cable ducts, fiber-optic relocation, cable trays, municipal utility networks, construction documents, financial records, materials, deadlines, Telegram communications, and unstructured project information.

### Key Characteristics
- **Local deployment**: Runs on local hardware (RTX 5060 with Ollama)
- **Privacy-preserving**: All data stays local
- **Multi-model execution**: DAYTIME/NIGHTTIME switching prevents VRAM conflicts
- **Telegram integration**: Natural language interface
- **Document processing**: PDF, DOCX, Excel parsing
- **Real-time monitoring**: GUI with health checks

## Technology Stack

### Core Technologies
- **Python 3.12**: Main programming language
- **Tkinter/ttk**: GUI framework
- **SQLite**: Database storage
- **Pydantic v2**: Data validation and schemas
- **llama.cpp**: Primary local LLM inference (llama-server, OpenAI-compatible API, port 8080)
- **Ollama**: Legacy/local LLM inference (Gemma 3 12B / Qwen 3 Coder 14B)
- **ChromaDB**: Vector storage for RAG
- **python-telegram-bot**: Telegram bot integration
- **APScheduler**: Task scheduling
- **PyMuPDF**: PDF processing
- **python-docx**: DOCX processing
- **openpyxl/xlrd**: Excel processing
- **psutil**: Process management

### Deployment Environment
- **OS**: Windows
- **GPU**: RTX 5060
- **Models**: 
  - DAYTIME: qwen2.5:14b-instruct (Primary Chat)
  - NIGHTTIME: qwen2.5-vl:7b (Vision/OCR monopoly slot)
  - bge-m3 (embeddings)
- **Multi-Model Pipeline**: Day/Night switching prevents VRAM OOM on single-GPU RTX 5060

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Mia PM OS GUI                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ Control  │ │  Queue   │ │  VRAM    │ │Questions │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                  │
│  │Telegram  │ │  Health  │ │   Logs   │                  │
│  └──────────┘ └──────────┘ └──────────┘                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   System Components                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Worker Pool  │  │ VRAM Policy  │  │Questions GW  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Audit Vector │  │Doctor Observer│  │Telegram Bot  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      Data Layer                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ SQLite DB    │  │ ChromaDB     │  │ File System  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    External Services                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Ollama API   │  │Telegram API  │  │ Documents    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## Component Architecture

### 1. GUI Layer (`gui/mia_gui.py`)

**Purpose**: User interface for system management and monitoring

**Key Features**:
- 6 tabs: Control, Queue, VRAM, Questions, Telegram, Health, Logs
- Single-instance enforcement (TCP socket lock on port 57423)
- Real-time status updates
- Telegram chat log display
- System control (start/stop/restart)

**Key Classes**:
- `MiaGUI`: Main GUI class
- `SingleInstanceChecker`: Prevents multiple instances

**Pipelines**:
- System startup → Component initialization → Telegram bot launch
- Periodic refresh → Status updates → Queue stats → Telegram chat

### 2. Worker Pool (`app/workers/worker_pool.py`)

**Purpose**: Single-threaded LLM task execution with priority scheduling

**Key Features**:
- Single worker/inference execution path
- Priority levels 10-1 (10 = highest)
- Worker states: IDLE, PROCESSING, PAUSED, STOPPED, ERROR
- Per-task suspension for human answers
- Integration with Questions Gateway and VRAM Policy

**Key Classes**:
- `SingleThreadedWorkerPool`: Main worker pool implementation
- `WorkerState`: Worker state enumeration

**Pipeline**:
```
Task Queue → Priority Scheduling → VRAM Slot Acquisition → 
Task Processing → Result Storage → Task Completion
```

### 3. VRAM Management (`app/modules/vram_policy.py`)

**Purpose**: GPU memory management for local LLM inference

**Key Features**:
- DAYTIME/NIGHTTIME execution modes
- Multi-model pipeline (explicit separation of chat and vision)
- Model slots: CHAT_MODEL, VISION_MODEL, HEAVY_VISION, NONE
- HEAVY_VISION monopoly behavior for nighttime OCR
- Priority-aware model selection
- Model-switch cooldown
- VRAM usage checks

**Multi-Model Configuration**:
- **DAYTIME Mode**: qwen2.5:14b-instruct (Primary Chat) - Active for user queries
- **NIGHTTIME Mode**: qwen2.5-vl:7b (Vision/OCR monopoly slot) - Exclusive for vision tasks
- **Rationale**: Single heavy multimodal models trigger VRAM OOM on RTX 5060. Day/Night switching prevents thrashing.

**Key Classes**:
- `VRAMManagementPolicy`: Main VRAM policy implementation
- `ExecutionMode`: Execution mode enumeration (DAYTIME, NIGHTTIME)
- `ModelSlot`: Model slot enumeration

**Pipeline**:
```
Task Request → Mode Determination → Model Selection → 
Slot Acquisition → Model Loading → Inference → Slot Release
```

### 4. Questions Gateway (`app/modules/storage/questions_gateway.py`)

**Purpose**: Human intervention system for critical decisions

**Key Features**:
- Typed question records with priorities
- Statuses: open, answered, deferred, invalid
- Shadow-IC file reading with mtime stability checks
- Regex validation of Markdown question blocks
- QUESTIONS.md generation/maintenance
- Per-task suspension and resumption

**Key Classes**:
- `QuestionsGateway`: Main questions gateway implementation
- `QuestionGatewaySchema`: Question data schema

**Pipeline**:
```
Critical Decision → Question Creation → QUESTIONS.md Update → 
Task Suspension → Human Answer → Task Resumption
```

### 5. Nighttime Audit Vector (`app/workers/audit_vector.py`)

**Purpose**: Background health checking for construction project consistency

**Key Features**:
- Nighttime execution mode
- 6 audit patterns: contract/document gaps, financial budget mismatches, 
  material status inconsistencies, deadline/document gaps, nomenclature conflicts, RAG white spots
- Automatic Questions Gateway creation for gaps requiring human action
- Audit statistics and gap persistence

**Key Classes**:
- `NighttimeAuditVector`: Main audit vector implementation
- `AuditGapSchema`: Audit gap data schema

**Pipeline**:
```
Nighttime Trigger → Pattern Execution → Gap Detection → 
Question Creation → Gap Persistence → Statistics Update
```

### 6. Doctor Observer (`app/modules/doctor/observer.py`)

**Purpose**: Real-time health monitoring and diagnosis

**Key Features**:
- Jaccard 3-gram similarity for repetition detection
- META_SLIP detection
- Worker-hang detection
- Response degradation detection
- G8 compliance (human approval for dangerous changes)
- Diagnosis persistence and recommended remediation

**Key Classes**:
- `DoctorObserver`: Main observer implementation
- `DoctorDiagnosisSchema`: Diagnosis data schema

**Pipeline**:
```
Health Monitoring → Pattern Detection → Diagnosis Generation → 
Recommendation → G8 Approval → Remediation Application
```

### 7. Database Layer (`app/modules/storage/database.py`)

**Purpose**: SQLite-based persistent storage

**Key Tables**:
- `projects`: Project information
- `llm_task_queue`: Unified LLM task queue
- `financial_reports`: Financial data
- `material_status`: Material tracking
- `document_metadata`: Document processing results
- `deadline_registry`: Deadline management
- `extracted_events`: Event extraction
- `nomenclature_mapping`: Material name standardization
- `questions_gateway`: Human intervention questions
- `audit_gaps`: Audit vector findings
- `doctor_diagnoses`: Doctor observer diagnoses
- `telegram_messages`: Telegram message log
- `project_ledger`: Chronological state-machine ledger for document versions, TU amendments, and chat updates
- `objects` / `diary_events`: Object diaries (RFC Object Diary v1.9)
- `constraints` / `constraint_history` / `constraint_dependencies`: Constraint network
- `virtual_documents`: Expected-but-not-yet-received documents
- `object_events`: Diary event stream (deadlines, risks, status changes)
- `invoices`: Financial ledger entries per object
- `contract_links`: Contract-to-object links with confidence and verification metadata
- `document_links`: Document-to-object links with citation metadata

**Project Ledger Schema**:
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

**Ledger Concept**: A chronological state-machine ledger that handles document versions, technical specification (ТУ) amendments, and chat updates sequentially. Ensures latest revisions block obsolete text chunks during vector/RAG searches.

**Key Functions**:
- `initialize_database()`: Table creation and indexing
- `enqueue_task()`: Task queue operations
- `get_queue_statistics()`: Queue monitoring
- `insert_telegram_message()`: Telegram message storage
- `get_recent_telegram_messages()`: Message retrieval

### 8. Telegram Bot (`mia/bot/main.py`)

**Purpose**: Natural language interface via Telegram

**Key Features**:
- Command handlers: /start, /help, /stats
- Document processing (PDF, DOCX, Excel)
- Voice message handling
- Text message processing with AI responses
- ~~RAG integration via AnythingLLM~~ (DEPRECATED - use native Hybrid RAG)
- Document summarization
- Registry generation

**Key Handlers**:
- `commands.py`: Command handlers
- `messages.py`: Text message processing
- `documents.py`: Document processing

**Pipeline**:
```
Telegram Message → Message Validation → Memory Storage → 
Intent Detection → Response Generation → Telegram Reply
```

### 8b. PM OS Telegram Bot (`app/bot/main.py`)

**Purpose**: Telegram front-end for the Mia PM OS runtime (primary system).

**Key Features**:
- LLM via **llama.cpp** (`LLAMA_BASE_URL`, OpenAI-compatible API) through
  `app/modules/llm/llama_cpp_client.py`.
- Delegation ("Спроси у Светы"): `PmOsAssistant` intercepts answers to delegated
  questions, detects new delegation requests (`DelegationEngine.try_parse_delegation`),
  otherwise answers via LLM.
- Proactive alerts: daily digest (10:00), critical objects (16:00) and cron tasks
  via `AlertDispatcher` started in `post_init` / stopped in `post_shutdown`.
- Commands: `/start`, `/help`, `/status`.
- **Safety**: `TELEGRAM_ALLOWLIST_ONLY=true` (default) — outgoing messages go only
  to `TELEGRAM_OWNER_CHAT_ID`; all other recipients are blocked and logged. If the
  owner is unset, nothing is sent. Use `/here` to discover your chat_id.
- On startup, `seed_roles_from_employees()` populates `system_roles` from
  `config/employees.json` (idempotent) so delegation can resolve people by name.

**Run**: `python -m app.bot.main` (token from `.env` → `BOT_TOKEN`).

### 9. Memory System (`mia/memory/`)

**Purpose**: Persistent message storage and semantic search

**Components**:
- `database.py`: SQLite message storage
- `memory_service.py`: Memory management
- `vector_store.py`: ChromaDB vector storage

**Pipeline**:
```
Message → Database Storage → Vector Embedding → 
Semantic Index → RAG Retrieval
```

### 10. Object Diary (`app/modules/object_diary/`)

**Purpose**: Per-object event diary, constraints, risk scoring and temporal reasoning
(RFC Object Diary v1.10, Jobs #1–#33).

**Modules** (17):
- `diary_manager.py` — CRUD for objects and `diary_events`, event overrides
- `constraint_manager.py` — Lean Construction constraint network
  (`NOT_SATISFIED` / `SATISFIED` / `WAIVED`), action gating via `can_proceed()`
- `health_score_engine.py` — cumulative risk: schedule, constraint, budget, silence
- `temporal_logic.py` — deadline parsing, schedule variance, burn rate
- `negative_event_trigger.py` — silence detection, overdue deadlines, question timeouts
- `telegram_distiller.py` — merges Telegram + documents + events into one timeline
- `document_linker.py`, `contract_analyzer.py`, `virtual_documents.py` — document pipeline
- `expert_teacher.py` — Human-in-the-loop lessons (Live Ontology of Deviations)
- `role_router.py`, `inbox_manager.py`, `knowledge_graph.py`, `pre_object_tracker.py`,
  `intent_classifier.py`, `constraint_health_integration.py`, `alert_dispatcher.py`

**Data**: `objects`, `diary_events`, `constraints`, `constraint_history`,
`constraint_dependencies`, `virtual_documents`, `object_events`, `invoices`,
`document_links`, `object_edges`, `expert_lessons`, `inbox_items`.

**Temporal module** (`app/modules/temporal/`) is separate: `TemporalLogicManager`
(Absolute Time Injection, relative dates, cron tasks), `AlertDispatcher` (APScheduler),
`TemporalAlertIntegration`.

## Data Flow Architecture

### Telegram Message Processing Pipeline

```
┌─────────────┐
│ User Message │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│      Telegram Bot (mia/bot/main.py)      │
│  - Message validation                    │
│  - Intent detection                     │
│  - Memory storage (mia/memory/)         │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│     Task Queue (app/modules/storage/)    │
│  - Task creation with priority           │
│  - Context attachment                   │
│  - Queue persistence                    │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│    Worker Pool (app/workers/)           │
│  - Priority scheduling                  │
│  - VRAM slot acquisition                │
│  - Task execution                       │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│     LLM Inference (Ollama)              │
│  - Model selection                      │
│  - Context injection                    │
│  - Response generation                  │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│     Response Processing                  │
│  - Result storage                       │
│  - Telegram reply                       │
│  - Memory update                        │
└─────────────────────────────────────────┘
```

### Document Processing Pipeline

```
┌─────────────┐
│  Document   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│   Document Handler (mia/bot/handlers/)  │
│  - File validation                      │
│  - Type detection                       │
│  - Storage                              │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│   Text Extraction (mia/documents/)      │
│  - PDF text extraction (PyMuPDF)        │
│  - DOCX processing (python-docx)        │
│  - Excel processing (openpyxl)          │
│  - OCR for scans (tesseract)           │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│   Summarization (mia/documents/)        │
│  - Text summarization                   │
│  - Key entity extraction                │
│  - Metadata generation                 │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│   Database Storage                     │
│  - Document metadata                    │
│  - Extracted text                       │
│  - Processing status                    │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│   Vector Embedding (ChromaDB)           │
│  - Text chunking                        │
│  - Embedding generation                │
│  - Semantic indexing                   │
└─────────────────────────────────────────┘
```

### Health Monitoring Pipeline

```
┌─────────────────────────────────────────┐
│   Doctor Observer (Continuous)          │
│  - Response tracking                   │
│  - Jaccard 3-gram analysis              │
│  - META_SLIP detection                 │
│  - Worker hang detection               │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│   Diagnosis Generation                  │
│  - Pattern matching                     │
│  - Severity assessment                  │
│  - Recommendation creation              │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│   G8 Approval Process                  │
│  - Questions Gateway integration         │
│  - Human approval required              │
│  - Safe remediation                    │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│   Nighttime Audit Vector (Scheduled)    │
│  - Contract/document gap check         │
│  - Financial budget validation         │
│  - Material status consistency          │
│  - Deadline/document gap detection     │
│  - Nomenclature conflict analysis       │
│  - RAG white spot detection             │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│   Gap Analysis & Reporting             │
│  - Critical gap identification           │
│  - Question generation                 │
│  - Audit statistics                     │
└─────────────────────────────────────────┘
```

## Configuration Management

### Environment Variables (.env)

```bash
# Telegram
BOT_TOKEN=<your-bot-token>
BOT_USERNAME=@mia_assistant_wd_bot
# Outgoing messages go ONLY to this chat_id (send /here to learn it)
TELEGRAM_OWNER_CHAT_ID=
TELEGRAM_ALLOWLIST_ONLY=true

# Ollama (legacy bot mia/)
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=qwen2.5:14b-instruct
EMBED_MODEL=bge-m3
LLM_TEMPERATURE=0.6
LLM_MAX_TOKENS=1200
LLM_TIMEOUT=300

# llama.cpp (primary LLM for Mia PM OS)
LLAMA_BASE_URL=http://localhost:8080
LLAMA_MODEL=qwen2.5:14b-instruct
LLAMA_EMBED_MODEL=

# Proactive alerts (PM OS)
ALERTS_ENABLED=true
ALERTS_CHAT_ID=

# Data
DATA_DIR=data

# Time
TIMEZONE=Europe/Moscow
```

### Runtime Configuration (`config/settings.py`)

- Database paths
- Directory structure
- Model configurations
- API endpoints

## Startup Sequence

### GUI Startup

1. **Single Instance Check**: TCP socket lock on port 57423
2. **Component Initialization**:
   - Questions Gateway database
   - Audit Vector database  
   - Doctor Observer database
3. **GUI Construction**: Create tabs and controls
4. **System Ready State**: Wait for user to start system

### System Startup (START SYSTEM button)

1. **VRAM Policy Initialization**: DAYTIME/NIGHTTIME mode setup
2. **Worker Pool Start**: Single-threaded worker initialization
3. **Questions Gateway Start**: QUESTIONS.md setup
4. **Audit Vector Start**: Background audit scheduling
5. **Doctor Observer Start**: Health monitoring initialization
6. **Telegram Bot Launch**: Subprocess with PYTHONPATH configuration
7. **System Running State**: All components active

## Single Instance Protection

### Implementation

- **Mechanism**: TCP socket binding on port 57423
- **Lock File**: `mia_instance.lock` (informational)
- **Cleanup**: Automatic stale lock removal
- **Release**: On clean shutdown and process termination

### Protection Goals

- Prevent VRAM conflicts on RTX 5060
- Avoid database corruption
- Eliminate queue processing conflicts
- Ensure single Telegram bot instance

## Error Handling and Recovery

### Database Errors
- Automatic retry with exponential backoff
- Connection pooling with thread safety
- Idempotent table creation

### LLM Errors
- Task suspension on timeout
- Retry with cooldown
- VRAM slot cleanup on failure

### Telegram Errors
- Conflict detection and self-termination
- Graceful degradation
- Message retry logic

### Worker Errors
- Per-task error isolation
- Failed task marking
- Worker state recovery

## Security Considerations

### Data Privacy
- All data stored locally
- No external API calls (except Telegram)
- No cloud dependencies
- User-controlled data retention

### Access Control
- RBAC ready (implementation pending)
- Project-based data isolation
- Telegram user authentication

### Integrity
- Pydantic v2 schema validation
- Database constraints
- File mtime stability checks
- Regex validation for critical inputs

## Performance Optimizations

### VRAM Management
- Single model loading discipline
- Model slot preemption
- Vision model unloading
- Priority-based model selection

### Database
- Indexed queries
- Connection pooling
- Batch operations
- Prepared statements

### Task Processing
- Priority scheduling
- Lazy loading
- Caching where appropriate
- Background processing

## Monitoring and Observability

### GUI Monitoring
- Real-time status updates
- Queue statistics
- VRAM slot status
- Health indicators
- Telegram chat log
- System logs

### Logging
- Structured logging with timestamps
- Component-level log files
- Error tracking
- Performance metrics

### Health Checks
- Doctor Observer continuous monitoring
- Nighttime Audit Vector scheduled checks
- Manual health check triggers
- Diagnosis persistence

## Deployment Notes

### System Requirements
- Windows OS
- Python 3.12+
- RTX 5060 GPU (8GB+ VRAM recommended)
- Ollama installation
- ~10GB disk space

### Installation
1. Clone repository to `C:\mia`
2. Install dependencies: `pip install -r requirements.txt`
3. Configure `.env` file
4. Start Ollama with required models
5. Run via GUI shortcut or `python gui/mia_gui.py`

### Model Setup
```bash
ollama pull qwen2.5:14b-instruct
ollama pull qwen2.5-vl:7b
ollama pull bge-m3
```

## Future Enhancements

### Planned Features
- RBAC implementation
- Natural language Telegram control for system operations
- Production Telegram/agent runtime integration
- Complete document workflow automation
- ~~Advanced RAG with AnythingLLM~~ (DEPRECATED - native Hybrid RAG implemented)
- Multi-project support
- Web interface alternative

### Technical Debt
- ~~Remove deprecated AnythingLLM references~~ (COMPLETED - native Hybrid RAG handles exact construction queries, tables, and document structures without external web-service overhead)
- ~~Modernize remaining Pydantic schemas to ConfigDict~~ (COMPLETED - all schemas use `model_config = ConfigDict(...)`)
- ~~Resolve single-model vs multiple day/night model contradictions~~ (COMPLETED - explicit multi-model pipeline: DAYTIME qwen2.5:14b-instruct, NIGHTTIME qwen2.5-vl:7b)
- Improve error recovery mechanisms
- Add comprehensive integration tests
- PostgreSQL migration for transactional load (DEFERRED, requires external setup — Todo.md 9.11)

## File Structure

```
C:\mia\
├── app/
│   ├── core/
│   │   └── schemas.py              # Pydantic v2 schemas
│   ├── modules/
│   │   ├── storage/
│   │   │   ├── database.py        # SQLite database layer
│   │   │   └── questions_gateway.py # Human intervention
│   │   ├── object_diary/          # RFC Object Diary v1.9 (17 modules)
│   │   │   ├── diary_manager.py
│   │   │   ├── constraint_manager.py
│   │   │   ├── health_score_engine.py
│   │   │   ├── temporal_logic.py
│   │   │   ├── telegram_distiller.py
│   │   │   └── ...
│   │   ├── temporal/              # Absolute Time Injection + cron tasks
│   │   │   ├── temporal_logic.py
│   │   │   ├── alert_dispatcher.py
│   │   │   └── temporal_alert_integration.py
│   │   ├── rag/                   # ChromaDB RAG (state replay, ingest)
│   │   ├── google_drive/          # OAuth, scanning, classification
│   │   ├── financial/             # Ledger integration
│   │   ├── doctor/
│   │   │   └── observer.py        # Health monitoring
│   │   └── vram_policy.py          # GPU memory management
│   └── workers/
│       ├── worker_pool.py          # Task execution
│       └── audit_vector.py         # Nighttime audits
├── gui/
│   ├── __init__.py
│   └── mia_gui.py                 # Main GUI application
├── mia/
│   ├── bot/
│   │   ├── main.py                # Telegram bot entry point
│   │   └── handlers/
│   │       ├── commands.py        # Command handlers
│   │       ├── messages.py        # Message processing
│   │       └── documents.py       # Document processing
│   ├── memory/
│   │   ├── database.py            # Message storage
│   │   ├── memory_service.py      # Memory management
│   │   └── vector_store.py        # Vector storage
│   └── documents/
│       ├── extractor.py           # Document extraction
│       ├── ocr.py                 # OCR processing
│       └── summarizer.py          # Document summarization
├── tests/
│   ├── test_schemas.py            # Schema validation tests
│   ├── test_queue.py              # Queue and worker tests
│   ├── test_questions.py          # Questions gateway tests
│   ├── test_autonomous_health.py  # Health monitoring tests
│   ├── test_safe_tool_layer.py    # Semantic tools (31 tests)
│   ├── test_state_replay_overrides.py # Ledger replay / overrides (17 tests)
│   ├── test_document_classifier.py    # Google Drive classifier (31 tests)
│   ├── test_object_diary.py       # Object Diary modules (119 tests)
│   ├── test_temporal_module.py    # Temporal module (33 tests)
│   ├── test_delegation_accuracy.py    # Delegation engine / accuracy contour (29 tests)
│   ├── test_document_pipeline.py      # Parsers, extractor, RAG ingestion (93 tests)
│   ├── test_llm_clients.py            # Ollama client / llama.cpp manager (38 tests)
│   ├── test_stub_integrations.py      # De-stubbed integrations (25 tests)
│   ├── test_llama_cpp_client.py       # llama.cpp client (23 tests)
│   ├── test_telegram_sender.py        # TelegramSender adapter (9 tests)
│   ├── test_bot_assistant.py          # PM OS assistant orchestrator (11 tests)
│   ├── test_alert_dispatcher_wiring.py # PM OS alert wiring (3 tests)
│   ├── test_seed_roles.py             # system_roles seeding (4 tests)
│   └── test_google_drive_financial.py # Drive ledger, contracts, finance (68 tests)
├── config/
│   ├── settings.py                # Configuration management
│   └── runtime.py                # Runtime configuration
├── data/
│   └── mia_pm.db                  # SQLite database
├── .env                           # Environment variables
├── requirements.txt               # Python dependencies
├── architecture.md               # This file
└── Todo.md                       # Implementation checklist
```

## Key Design Decisions

### Single-Threaded Execution
- **Decision**: Single worker for LLM execution
- **Rationale**: Prevent VRAM conflicts on local GPU
- **Trade-off**: Limited parallelism, but guaranteed stability

### Local-First Architecture
- **Decision**: All data processing locally
- **Rationale**: Privacy preservation and offline capability
- **Trade-off**: Limited cloud integration, higher local resource requirements

### Priority-Based Task Scheduling
- **Decision**: 10-level priority system
- **Rationale**: Ensure critical tasks processed first
- **Trade-off**: Lower priority tasks may wait longer

### Telegram as Primary Interface
- **Decision**: Natural language via Telegram
- **Rationale**: User familiarity and mobile accessibility
- **Trade-off**: Limited UI capabilities compared to web GUI

### Separation of Concerns
- **Decision**: Modular component architecture
- **Rationale**: Maintainability and testability
- **Trade-off**: Increased complexity in inter-component communication

## Integration Points

### External Systems
- **Ollama**: LLM inference API
- **Telegram Bot API**: Message handling
- **File System**: Document storage
- **ChromaDB**: Vector storage (future enhancement)

### Internal Integration
- **Worker Pool ↔ VRAM Policy**: Model slot management
- **Worker Pool ↔ Questions Gateway**: Task suspension/resumption
- **Doctor Observer ↔ Questions Gateway**: Approval workflow
- **Audit Vector ↔ Questions Gateway**: Gap reporting
- **Telegram Bot ↔ Memory System**: Message storage

## Troubleshooting Guide

### Common Issues

**Bot not receiving messages**
- Check Telegram bot process status
- Verify BOT_TOKEN in .env
- Check telegram_bot.log for errors
- Ensure no other bot instance running

**VRAM conflicts**
- Check model slot status in GUI
- Verify Ollama is running
- Review VRAM policy configuration
- Check for stuck model loading

**Database errors**
- Verify data directory exists
- Check database file permissions
- Review database initialization logs
- Check for concurrent access issues

**Performance issues**
- Monitor queue backlog
- Check worker pool status
- Review VRAM usage
- Consider task priority adjustments

## Maintenance

### Regular Tasks
- Monitor telegram_bot.log for errors
- Review Doctor Observer diagnoses
- Check Audit Vector gaps
- Verify database integrity
- Monitor VRAM usage patterns

### Backup Strategy
- Regular database backups (mia_pm.db)
- Configuration file backup (.env)
- Document repository backup
- Vector database backup (ChromaDB)

### Updates
- Check for dependency updates
- Review model updates in Ollama
- Test compatibility before deployment
- Update architecture documentation

---

**Document Version**: 1.0  
**Last Updated**: 2026-08-31  
**Maintained By**: Devin AI Assistant  
**Purpose**: System architecture reference for development and maintenance