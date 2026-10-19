# Changelog

## 2026-10-19

### Added
- **Object Diary: тесты и починка схемы** (`tests/test_object_diary.py` — 119 тестов):
  ConstraintManager, IntentClassifier, HealthScoreEngine, TemporalLogic, AlertDispatcher,
  InboxManager, KnowledgeGraph, VirtualDocuments, PreObjectTracker, ExpertTeacher,
  RoleRouter, NegativeEventTrigger, ConstraintHealthIntegration, ContractAnalyzer,
  DocumentLinker, TelegramDistiller, DiaryManager + импортируемость всех 17 модулей.
- **Temporal module: тесты** (`tests/test_temporal_module.py` — 23 теста):
  TemporalLogicManager (relative dates, Absolute Time Injection, cron tasks),
  AlertDispatcher, TemporalAlertIntegration.
- **Схема БД**: добавлены отсутствовавшие таблицы `object_events` (event_id, object_id,
  event_type, event_date, deadline_date, description, status, metadata) и `invoices`
  (invoice_id, object_id, amount, date, status, description) + индексы.
- **Safe Tool Generation Layer (Job #6.10)**:
  - `SafeToolLayer.parse_tool_call` / `execute_tool_call` — автоматический JSON-парсинг
    tool-call от LLM (dict, JSON-строка, fenced ```json``` блок, альтернативные ключи
    `tool_name`/`arguments`/`params`).
  - Семантические параметризованные инструменты вместо сырого SQL:
    `search_objects`, `get_object_events`, `get_health_score`, `search_messages`
    (все read-only, SQL с плейсхолдерами `?`, лимиты ограничены).
  - Инструмент `query_database` (сырой SELECT) удалён.
- **Тесты**:
  - `tests/test_safe_tool_layer.py` — 31 тест (парсинг, валидация, permissions,
    семантические инструменты, инертность SQL-инъекций);
  - `tests/test_state_replay_overrides.py` — 17 тестов (State Replay, Chunk Versioning,
    Override Detection, Document Override Manager).

### Changed
- **Google Drive Document Classifier** (RFC Google Drive Analysis):
  - Нормализация разделителей в именах файлов (`_ - . ( ) [ ] # , +` → пробел) —
    `\b`-границы теперь работают для `паспорт_трассы`, `РД-01`, `паспорт (4).pdf` и т.п.
  - Исправлены **дубли ключей** в `PATTERNS` — поздние записи `passport`, `project`,
    `invoice`, `estimate` затирали ранние (русские паттерны `паспорт`/`проект`
    не срабатывали вообще).
  - Добавлены паттерны по топовым реальным именам из скана: титул, обложка,
    содержание, ведомость, профиль, вынос, сборочный, узел/деталь, сертификат,
    выписка, журнал, акт сверки, доверенность, разработка, грунт, труба/пайп,
    обратная засыпка, реестр, поручение, платежное, муфта, канализация и др.
  - Extension-fallback: `.dwg/.dxf` → `cad_drawing`, служебные AutoCAD-файлы
    (`.shx/.bak/.sig/.ctb/...`) → `cad_service`, картинки → `image`, архивы → `archive`.
  - Приоритетные типы (`_PRIORITY_TYPES`): специфичные паттерны проверяются раньше
    generic («Титул_проекта» → `titul`, а не `project`; «Акт_сверки» → `akt_sverki`).
  - Кэш скомпилированных regex (`_COMPILED`) — классификация 30597 файлов: 134s → 5.6s.
  - **Результат на реальном скане** (`google_drive_scan_result_reclassified.json`,
    30597 файлов): unknown **70.7% → 16.4%**.
  - Тесты: `tests/test_document_classifier.py` — 31 тест (нормализация, паттерны,
    CAD-расширения, batch, smoke на реальном скане с порогом unknown < 25%).
- **Job #37**: подтверждено — `query_structured_db` отсутствует и в коде, и в
  актуальной документации (остались только в описании самой джобы и в `docs/archive/`).
- **Job #6.11**: подтверждено — все Pydantic-схемы уже используют
  `model_config = ConfigDict(...)`; class-based `Config` в коде отсутствует.
- **Todo.md**: статусы 6.10, 6.11, 7.14, 7.15 обновлены (были DEFERRED, фактически
  реализованы; 7.14/7.15 закрыты починкой и тестами).

### Fixed
- **Object Diary: модули писали в несуществующую схему БД** — 12 модулей падали
  на импорте/выполнении. Переписаны под реальную схему (`database.py` — источник истины):
  - `constraint_health_integration.py` — сломанный импорт `ConstraintCheckResult`/`RiskZone`
    (пакет `object_diary` вообще не импортировался);
  - `constraint_manager.py` — `constraint_name`, `required_for_actions` JSON,
    статусы `NOT_SATISFIED`/`SATISFIED`/`WAIVED` (+ алиасы `BLOCKING`/`RESOLVED`/`IGNORED`),
    `constraint_history`;
  - `virtual_documents.py` — `virtual_doc_id`, `diary_id`, `actual_doc_id`,
    `actual_received_at`, статусы в uppercase;
  - `expert_teacher.py` — `doc_category`, `context_tags`, `raw_page_text`,
    `anchor_text_embedding_id`, `expert_commentary`, `applicability_scope`, `verified_by_human`;
  - `health_score_engine.calculate_constraint_risk` — фильтр `NOT_SATISFIED` вместо `blocking`;
  - `telegram_distiller.py` — чтение `message_text` и резолв чата через `projects`
    (`telegram_chat_id`/`google_drive_folder_id`), дедупликация рисков и таймлайна,
    `prioritize_sources` больше не затирает риск-приоритет;
  - `contract_analyzer.py` — парсинг номера с кириллицей, даты и суммы с разделителями тысяч.
- **Битые импорты `DocumentParser`** (`document_info_extractor.py`,
  `object_diary/contract_analyzer.py`, `rag/document_ingestor.py`): класс не имеет
  `parse_document` — заменён на `DocumentParserFactory`; `extract_all` теперь возвращает `raw_text`.
- **`app/modules/temporal`**: `__init__.py` импортировал несуществующие
  `temporal_logic.py`/`alert_dispatcher.py` (лежали в `archive/` как `*_duplicate.py`) —
  модули восстановлены, пакет импортируется; добавлен пропущенный `List` в typing.
- **`gui/mia_gui.py:551`**: импортировался `TemporalLogic`, вызывался
  `TemporalLogicManager` → `NameError` при каждом сообщении в чате.
- `temporal_logic.inject_absolute_time` — «2 weeks» давал 60 дней вместо 14.
- `alert_dispatcher.py` — отсутствовал `timedelta` в импорте.
- `diary_manager.update_diary` — перепутанный порядок параметров (`WHERE diary_id`).
- `intent_classifier` — скоринг по длине ключевого слова («Запусти бота» → `system_control`).
- `negative_event_trigger` — `questions` → `questions_gateway` со статусами `NOT IN ('answered','resolved')`.
- **VRAM Policy**: ночью задачи с приоритетом 1/3 теперь маршрутизируются на vision-модель
  (`qwen2.5-vl:7b`) даже в single-model режиме — дневная конвейерная линия
  DAYTIME chat / NIGHTTIME vision (docs/jobs_stage6_coder.md, Этап 6.5).
  Тест `tests/test_queue.py::TestVRAMPolicy::test_model_selection_for_task` теперь проходит.
- **State Replay Engine (7.14)**: исправлены две ошибки ChromaDB:
  - nested dict в metadata → сериализация в JSON (ChromaDB принимает только скаляры);
  - несколько условий в `where` → оператор `$and` (требование chromadb 1.5).
- **Chunk Version Manager**: `add_versioned_chunks` теперь вызывает
  `mark_chunks_obsolete` — старые чанки действительно блокируются при поиске
  актуальных версий (`status: actual`).

### Test results
- **317 passed** (было 144 до изменений; +142 теста object_diary/temporal и др.).
