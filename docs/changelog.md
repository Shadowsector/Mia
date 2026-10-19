# Changelog

## 2026-10-19

### Fixed
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

### Added
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
- **Job #37**: подтверждено — `query_structured_db` отсутствует и в коде, и в
  актуальной документации (остались только в описании самой джобы и в `docs/archive/`).
- **Job #6.11**: подтверждено — все Pydantic-схемы уже используют
  `model_config = ConfigDict(...)`; class-based `Config` в коде отсутствует.
- **Todo.md**: статусы 6.10, 6.11, 7.14, 7.15 обновлены (были DEFERRED, фактически
  реализованы; 7.14/7.15 закрыты починкой и тестами).

### Test results
- 144 passed (было 95 passed / 1 failed до изменений).
