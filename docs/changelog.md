# Changelog

## 2026-10-19

### Added
- **Замена заглушек реальной интеграцией** (item 2; тесты — `tests/test_stub_integrations.py`, 25):
  - `DelegationEngine` — LLM-парсинг запроса (`PromptTemplates.delegation_extraction_prompt`),
    классификация ответа vs трёп (`delegation_answer_classifier_prompt`), создание задачи
    в Inbox (`questions_gateway`) при неоднозначном имени, отправка через инъектируемый
    `telegram_sender` (`send`, `can_send_private` → PRIVATE/PUBLIC, @упоминание), fallback
    в лог без Telegram.
  - `AccuracyContourManager` — Метод 2 реально ищет справочные документы в RAG
    (`search_between_objects`/`query`/`search`) и сравнивает суммы/даты спецификации
    (аномалии `amount_mismatch`/`date_mismatch`); Метод 3 через Ollama извлекает
    неформальные дедлайны и накладывает BYPASS при конфликте с официальным реестром.
  - `temporal.AlertDispatcher` — дайджест (10:00) и критические алерты (16:00) на основе
    `HealthScoreEngine`, cron-задачи через `TemporalLogicManager`, отправка через
    `telegram_sender`; `AlertSchema` получил реальные значения по умолчанию.
  - `TemporalLogicManager._execute_task_logic` — реальная классификация cron-задачи
    (`alert`/`report`/`health_check`/`document`/`generic`) с извлечением `object_id`
    (`OBJ-...`) и структурированным списком действий; `AlertDispatcher` и
    `TemporalAlertIntegration` используют `task_type` из результата.
  - `TemporalAlertIntegration` — дайджест собирает события дня из `DiaryManager` и статус
    из `HealthScoreEngine`; критический отчёт учитывает RED-объекты и блокирующие
    ограничения (`constraints.status = 'NOT_SATISFIED'`).
  - `FinancialLedgerIntegration` — источник `local` (реальное чтение таблицы `invoices`)
    и HTTP-коннектор `1c`/`erp` (`connect({base_url, token})` + `/payments`, `/invoices`).
- **Покрытие тестами 15 ранее непокрытых модулей** (+228 тестов):
  - `tests/test_delegation_accuracy.py` — 29 тестов: `DelegationEngine` (парсинг запроса,
    поиск по `system_roles`, разрешение неоднозначности, делегирование, перехват ответа,
    эскалация REMINDED/ESCALATED) и `AccuracyContourManager` (Метод 1 NetworkX,
    граф зависимостей, Метод 2/3, консенсус-арбитр, полный аудит).
  - `tests/test_document_pipeline.py` — 93 теста: `DocumentParserFactory` и все парсеры
    (PDF/Word/Excel/Text/Image), `DocumentInfoExtractor`, `DocumentIngestor`,
    `StructuredExcelParser` + `HybridRAG`, `ChromaManager`, `TempFileProcessor`,
    `GoogleDriveScanner`/`OAuthDriveScanner`.
  - `tests/test_llm_clients.py` — 38 тестов: `OllamaClient` (кэш, retry-обёртка,
    generate/generate_json/embedding), `PromptTemplates`, `LlamaCppManager`
    (start/stop, health-check, generate, stream, download_model).
  - `tests/test_google_drive_financial.py` — 68 тестов: `FinancialLedgerIntegration`,
    `FinancialHealthAnalyzer`, `ContractLinker`, `ProjectLedgerManager`,
    `KnowledgeSummarizer`, `DocumentProcessor`/`GoogleDriveDownloader`.
- **Схема БД**: добавлена таблица `contract_links` (+ индексы) — `ContractLinker`
  и `KnowledgeSummarizer` больше не падают на отсутствующей таблице.
- **Object Diary: тесты и починка схемы** (`tests/test_object_diary.py` — 119 тестов):
  ConstraintManager, IntentClassifier, HealthScoreEngine, TemporalLogic, AlertDispatcher,
  InboxManager, KnowledgeGraph, VirtualDocuments, PreObjectTracker, ExpertTeacher,
  RoleRouter, NegativeEventTrigger, ConstraintHealthIntegration, ContractAnalyzer,
  DocumentLinker, TelegramDistiller, DiaryManager + импортируемость всех 17 модулей.
- **Temporal module: тесты** (`tests/test_temporal_module.py` — 33 теста):
  TemporalLogicManager (relative dates, Absolute Time Injection, cron tasks + классификация
  `_execute_task_logic`), AlertDispatcher, TemporalAlertIntegration.
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
- **Багфиксы, найденные новыми тестами**:
  - `document_ingestor.chunk_text` — бесконечный цикл при `chunk_overlap >= chunk_size`
    и потеря последнего чанка; теперь прогресс гарантирован, текст покрывается полностью.
  - `chroma_manager` — `where` с несколькими условиями без `$and` и пустой `where={}`
    (ValueError в ChromaDB 1.5); `update_chunk_metadata` использовал несуществующий
    аргумент `metadata=` вместо `metadatas=`; `legal_entities` теперь JSON с `ensure_ascii=False`.
  - `delegation_engine` — запрос по несуществующей колонке `status` (нужен
    `escalation_status`); `deadline_for_reply`/`answer_timestamp`/`escalation_timestamp`
    пишутся как ISO-строки; напоминание отправляется после истечения дедлайна
    (раньше — через 4 часа сверх него) и больше не повторяется каждый цикл.
  - `contract_linker._load_objects` — `SELECT id` при реальной колонке `diary_id`
    (кэш объектов всегда был пуст); матчинг по вхождению ссылки в `object_id`.
  - `oauth_scanner.infer_document_type` — короткие ключи (`сп`, `пас`) перебивали
    длинные (`паспорт`); теперь побеждает самое длинное совпадение.
  - `project_ledger_manager._is_construction_object` — короткие exclude-ключи
    (`ак`, `ос`, `кк`) вырезали валидные адреса («Судакова 5», «Сергиев Посад»);
    для ключей ≤3 символов — совпадение только целым словом.
  - `google_drive/scanner` — вызовы без аутентификации падали с `AttributeError`
    (`self.service is None`); удалён мёртвый дублированный код в `list_files`.
  - `document_info_extractor` — суммы с разделителями тысяч («1,500,000.50»,
    «2.000.000,00», «250 000») парсились как 0.5/1.5/2.0; добавлен `_parse_amount`,
    дедупликация, даты «15 марта 2024» и контекстные даты договора/завершения
    (сравнение с исходным форматом, а не ISO); `заказчик`/`подрядчик`/`объект`
    больше не захватывают следующие строки.
  - `structured_excel_parser` — `to_markdown` требовал необъявленный `tabulate`;
    добавлен fallback-рендер markdown-таблицы.
  - `ollama_client.PromptTemplates.temporal_context_prompt` — `replace(day=day+1)`
    падал в конце месяца/года; переведено на `timedelta`.
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
- **580 passed** (было 317 в начале дня; +263 теста): покрытие 15 модулей (+228),
  интеграционные тесты de-stub (+25) и тесты cron-логики (+10).
