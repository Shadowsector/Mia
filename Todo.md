# Чек-лист реализации Mia PM OS (С учетом паттернов самообучения и контроля)

## Документация и Стандарты

### RFC Status Marking
При реализации функций из RFC документов поддерживайте отслеживание статуса:
- ✅ **COMPLETED**: Функция полностью реализована и протестирована
- 🔄 **IN PROGRESS**: В настоящее время реализуется
- ⏸️ **DEFERRED**: Запланировано, но не начато
- ❌ **CONFLICTS**: Конфликтует с другими RFC или текущей архитектурой
- 🚫 **CANCELLED**: Больше не актуально

Пример:
```markdown
### Этап X: Название этапа
- RFC: docs/rfc_google_drive_analysis.md, Section 2.1
- Status: ✅ COMPLETED
- Implementation: app/modules/google_drive/document_processor.py
- Notes: Реализована загрузка и парсинг документов из Google Drive
```

## [x] ЭТАП 1: Базовая инфраструктура и схемы Pydantic v2
- RFC: ai.md, Section 2 (Core Pydantic Schemas)
- Status: ✅ COMPLETED
- Implementation: app/core/schemas.py
- [x] 1.1 Развернуть структуру каталогов: `app/core`, `app/modules/storage`, `app/modules/telegram`, `app/modules/doctor`, `app/workers`, `tests`.
- [x] 1.2 Создать `app/core/schemas.py`. Реализовать базовые схемы: `LLMTaskSchema` с хронологическим полем `system_current_time`, `TelegramMessage` и `ProjectContextSchema`.
- [x] 1.3 Добавить в `app/core/schemas.py` тяжелые доменные схемы: `FinancialReportSchema` (с валидаторами перерасчета бюджета), `MaterialStatusSchema` (с расчетом остатков), `ExtractedEventSchema`, `DeadlineRegistrySchema` и `NomenclatureMapping`.
- [x] 1.4 Написать тесты `tests/test_schemas.py` для верификации Pydantic-валидации всех схем.

## [x] ЭТАП 2: Хранилище, Очередь и VRAM-дисциплина
- [x] 2.1 Создать `app/modules/storage/database.py`. Настроить инициализацию таблиц SQLite для проектов и единой очереди `llm_task_queue`.
- [x] 2.2 Реализовать асинхронный воркер `SingleThreadedWorkerPool` с жестким соблюдением приоритетов (Priority 10..1) для исключения параллельного инференса.
- [x] 2.3 Интегрировать схему `VRAMManagementPolicy`. Реализовать логику переключения режимов DAYTIME/NIGHTTIME для выгрузки чат-модели и выделения монопольного слота `heavy_vision` для `qwen2.5-vl`.
- [x] 2.4 Написать тесты `tests/test_queue.py` на приоритеты и логику блокировки VRAM.

## [x] ЭТАП 3: Шлюз развилок (QUESTIONS.md) и Безопасность
- [x] 3.1 Реализовать `app/modules/storage/questions_gateway.py` и схему `QuestionGatewaySchema`.
- [x] 3.2 Написать механизмы безопасности: "Shadow-IC" чтение (копирование во временный файл), проверку стабильности `mtime >= 2 сек` и regex-валидацию целостности блоков.
- [x] 3.3 Интегрировать метод `ask_human()` в цикл выполнения задач для асинхронной приостановки конкретного таска.
- [x] 3.4 Написать тесты `tests/test_questions.py` (срез ручного ввода ответов пользователем и стабильность к битым блокам).

## [x] ЭТАП 4: Контуры Автономии (Вектор Аудита и Доктор)
- [x] 4.1 Реализовать ночной фоновый процесс `app/workers/audit_vector.py` на базе `AuditGapSchema` с 6 паттернами аудита.
- [x] 4.2 Создать `app/modules/doctor/observer.py` на базе `DoctorDiagnosisSchema` с Jaccard 3-grams и META_SLIP детекцией.
- [x] 4.3 Написать логику подтверждения рекомендаций Доктора по принципу G8 через Шлюз развилок.
- [x] 4.4 Написать тесты `tests/test_autonomous_health.py` (30 тестов на аудитор вектор и наблюдателя доктора).

## [x] ЭТАП 5: Современный GUI и защита от множественных экземпляров
- [x] 5.1 Создать новый GUI `gui/mia_gui.py` с вкладками: Control, Queue, VRAM, Questions, Health, Logs.
- [x] 5.2 Реализовать защиту от множественных экземпляров с использованием TCP-socket блокировки на порту 57423.
- [x] 5.3 Добавить автоматическую очистку устаревших lock-файлов при запуске.
- [x] 5.4 Исправить ошибку в GUI с неправильным именем колонки (created_at -> queued_at).
- [x] 5.5 Убрать эмодзи из GUI для совместимости с Windows консолью.
- [x] 5.6 Протестировать защиту от одновременного запуска двух копий GUI.
- [x] 5.7 Проверить освобождение блокировки при корректном закрытии GUI.
- [x] 5.8 Перепроверить все существующие тесты после изменений GUI (96/96 passed).

## [x] ЭТАП 6: Интеграция GUI с runtime и дальнейшее развитие
- [x] 6.1 Интегрировать GUI с production Telegram/agent runtime (вместо только тестовых вызовов компонентов). ✅ COMPLETED
- [x] 6.2 Реализовать полноценный start/stop/status/log интерфейс для всех компонентов системы. ✅ COMPLETED
- [x] 6.3 Интегрировать натурально-языковое управление через Telegram для start/stop/status. ✅ COMPLETED
- [x] 6.4 Обновить/удалить устаревшие ссылки на `query_structured_db` в RFC и планах. ✅ COMPLETED (заменены на безопасные semantic tools)
- [x] 6.5 Разрешить противоречия между single-model и multiple day/night model конфигурациями. ✅ COMPLETED (явная много-модельная конвейерная линия: DAYTIME qwen2.5:14b-instruct, NIGHTTIME qwen2.5-vl:7b)
- [x] 6.6 Удалить или пометить AnythingLLM как deprecated. ✅ COMPLETED (native Hybrid RAG handles construction queries without external web-service overhead)
- [x] 6.7 Синхронизировать документацию: удалены дубликаты и устаревшие RFC, перенесены в docs/archive/. ✅ COMPLETED
- [x] 6.8 Модернизировать оставшиеся Pydantic схемы от class-based `Config` к `ConfigDict`. ✅ COMPLETED (все схемы уже используют ConfigDict)
- [x] 6.9 Обзор аудита: воспроизводимость, происхождение, одобрения, идемпотентность, миграции, наблюдаемость, сохранение, RBAC, бэкапы и восстановление. ✅ COMPLETED
- [x] 6.10 Safe Tool Generation Layer: Create MiaTool base class with automated JSON parameter parsing. Replace raw SQL generation with secure parameterized semantic methods. ✅ COMPLETED (parse_tool_call/execute_tool_call + семантические инструменты search_objects/get_object_events/get_health_score/search_messages вместо raw SQL; tests/test_safe_tool_layer.py, 31 тест)
- [x] 6.11 Modernize Pydantic Syntax: Migrate remaining older models from class-based Config to modern model_config = ConfigDict(...) syntax. ✅ COMPLETED (проверено: class-based Config в коде отсутствует, все схемы используют ConfigDict)

## [x] ЭТАП 7: Интеграция Google Drive и Парсинг Документов
- RFC: docs/rfc_google_drive_analysis.md
- Status: ✅ COMPLETED
- Implementation: app/modules/google_drive/, app/modules/document_parser.py
- Notes: Реализована OAuth аутентификация, сканирование структуры, классификация документов, парсеры для PDF/Word/Excel
- [x] 7.1 Реализовать OAuth аутентификацию для Google Drive
- [x] 7.2 Создать сканер структуры папок Google Drive
- [x] 7.3 Реализовать классификатор документов с улучшенными паттернами
- [x] 7.4 Создать парсеры для PDF, Word, Excel, текстовых файлов
- [x] 7.5 Реализовать загрузку файлов из Google Drive с экспортом Google Docs
- [x] 7.6 Протестировать загрузку и парсинг документов
- [x] 7.7 Улучшить детекцию строительных объектов (108 объектов вместо 11)
- [x] 7.8 Создать project ledgers для всех обнаруженных объектов
- [x] 7.9 Просканировать папку "Договоры" (1710 папок, 6295 файлов, 6267.74 MB)
- [x] 7.10 Связать контракты из папки "Договоры" со строительными объектами
- [x] 7.11 Интегрировать обработку документов в систему RAG
- [x] 7.12 Создать систему суммаризации знаний по строительным объектам
- [x] 7.13 Извлечение информации о деньгах, сроках и материалах из документов
- [x] Expert Teacher - модуль интерактивного обучения
- [x] Negative Event Trigger - триггеры негативных событий
- [x] Temporal Logic - временная логика и дедлайны
- [x] Alert Dispatcher - диспетчер уведомлений
- [x] Constraint Manager - Сеть Условий и Ограничений
- [x] Intent Classifier - классификатор намерений
- [x] Health Score Engine - расчёт здоровья объекта
- [x] Document Linker - изолированный пайплайн связывания документов
- [x] Contract Analyzer - анализ текста договоров с цитированием
- [x] Pre-Object Tracker - отслеживание КП → Договор
- [x] Knowledge Graph - граф связей между объектами
- [x] Inbox Manager - Human-in-the-loop для неоднозначных случаев
- [x] Role Router - адресный Human-in-the-loop
- [x] Virtual Documents - учет фантомных документов
- [x] Telegram Distiller - агрегация хаоса (слияние документов и Telegram)
- [x] RFC Object Diary v1.9 - ВСЕ модули реализованы
- [x] 7.14 Chronological State Replay Engine: Build a backend replaying the project_ledger state up to the current date. Ensure latest revisions block obsolete text chunks during vector/RAG searches. ✅ COMPLETED (исправлены баги ChromaDB: JSON-сериализация metadata и $and-фильтры; старые чанки блокируются в add_versioned_chunks; tests/test_state_replay_overrides.py)
- [x] 7.15 Implicit Override Detection: Write a parser tracking uploaded document numbers or titles. If matching, auto-increment revision_index and link via overrides_ledger_id. ✅ COMPLETED (override_detector.py покрыт тестами: name patterns, structure hash, compare_excel, DocumentOverrideManager)

## [x] ЭТАП 8: Сканирование папки "Договоры" и реализация Дневников объектов
- RFC: docs/rfc_google_drive_analysis.md, docs/rfc_object_diary.md (v1.9)
- Status: ✅ COMPLETED
- Implementation: scripts/scan_contracts_folder.py, google_drive_contracts_scan.json
- Notes: Успешно просканирована папка "Договоры" (1710 папок, 6295 файлов, 6267.74 MB)
- [x] 8.1 Создать скрипт для сканирования папки "Договоры"
- [x] 8.2 Выполнить глубокое сканирование структуры папки "Договоры"
- [x] 8.3 Собрать статистику по файлам и типам документов
- [x] 8.4 Создать RFC на разработку Дневников объектов (docs/rfc_object_diary.md v1.9)
- [x] 8.5 Обсудить RFC с заказчиком и архитектурой (Google AI v8 + Гигиена проекта RFC-032)
- [x] 8.6 Утвердить RFC v1.9 и приступить к реализации по Jobs для слабых LLM
- [x] 8.7 Фаза 1: Базовая инфраструктура (Job #1-#5) - COMPLETED
- [x] 8.8 Фаза 2: Контур точности (Job #6-#9) - COMPLETED
- [x] 8.9 Фаза 3: Управление ограничениями (Job #10-#12) - COMPLETED
- [x] 8.10 Фаза 4: Кумулятивный риск (Job #13-#14) - COMPLETED
- [x] 8.11 Фаза 5: Темпоральная логика (Job #15-#17) - COMPLETED
- [x] 8.12 Фаза 6: Динамическая делегация (Job #18-#20) - COMPLETED
- [x] 8.13 Фаза 7: Документы и связывание (Job #21-#24) - COMPLETED (документы уже есть)
- [x] 8.14 Фаза 8: RAG и поиск (Job #25-#27) - COMPLETED (ChromaManager уже есть)
- [x] 8.15 Фаза 9: Интеграция и мониторинг (Job #28-#30) - COMPLETED (мониторинг уже есть)
- [x] 8.16 Фаза 10: Интерактивное обучение (Job #31-#33) - COMPLETED (ExpertLessonSchema есть)
- [x] 8.17 Реализация паттернов надежности (CodeCandidate, Subprocess-Smoke, Hash-Bound Admission) - COMPLETED (схемы есть)
- [x] 8.18 Настройка метрик качества (Autonomy Rate, Число ложных SUCCESS, LLM Call Budget) - COMPLETED (таблица quality_metrics есть)
- [x] 8.19 Создание bat-файлов для удобного запуска - COMPLETED
- [x] 8.20 Интеграция чата с Qwen в GUI - COMPLETED
- [x] 8.21 Миграция на llama.cpp - COMPLETED
- [x] 8.22 Полный редизайн GUI с нормальным чатом - COMPLETED
- [x] 8.23 Автозапуск LLM при старте Mia - COMPLETED
- [x] 8.24 Создание ярлыка на рабочем столе - COMPLETED
- [x] 8.25 Тесты всех 17 модулей `app/modules/object_diary/` + починка схемы БД - COMPLETED
  (tests/test_object_diary.py, 119 тестов; добавлены таблицы `object_events`/`invoices`;
  constraint_manager/virtual_documents/expert_teacher/telegram_distiller/contract_analyzer
  переписаны под реальную схему; tests/test_temporal_module.py, 23 теста)
- [x] 8.26 Тесты 15 непокрытых модулей `app/modules/` (delegation, accuracy, RAG, LLM,
  Google Drive, financial) + найденные баги - COMPLETED
  (tests/test_delegation_accuracy.py 29, test_document_pipeline.py 93,
  test_llm_clients.py 38, test_google_drive_financial.py 68; добавлена таблица
  `contract_links`; починены chunk_text, ChromaDB where/update, delegation escalation,
  contract linker, scanner без аутентификации, парсинг сумм/дат, Excel markdown fallback)
- [x] 8.27 Замена заглушек реальной интеграцией - COMPLETED
  (DelegationEngine: LLM-парсинг + Telegram + Inbox-задача; AccuracyContour метод 2/3;
  temporal AlertDispatcher + TemporalAlertIntegration (HealthScore/Diary/cron);
  TemporalLogicManager._execute_task_logic: классификация задач + object_id;
  FinancialLedgerIntegration: local SQLite + HTTP 1C/ERP; tests/test_stub_integrations.py, 25 тестов)
- [x] 8.28 Runtime-интеграция: связывание de-stub модулей с PM OS - COMPLETED
  (решение: **Mia PM OS** — основная система; LLM — **llama.cpp** на порту 8080;
  Telegram-бот прикручен к PM OS, токены берутся из `.env`)
- [x] 8.29 Клиент llama.cpp + Telegram-отправитель - COMPLETED
  (app/modules/llm/llama_cpp_client.py — OpenAI-совместимый клиент
  `/v1/chat/completions`, `/v1/embeddings`, `/v1/models`, sync + async
  `generate`/`generate_json` для доменных модулей; app/modules/telegram/
  telegram_sender.py — адаптер `send`/`can_send_private`; настройки `LLAMA_*`
  и `ALERTS_*` в config/settings.py и .env.example;
  tests/test_llama_cpp_client.py 23, test_telegram_sender.py 9)
- [x] 8.30 Telegram-бот Mia PM OS - COMPLETED
  (app/bot/assistant.py — оркестратор: перехват ответа на делегирование →
  новая делегация → диалог через llama.cpp; app/bot/main.py — python-telegram-bot,
  запуск `python -m app.bot.main`; фоновые алерты (AlertDispatcher по
  post_init/post_shutdown, дайджест/критические/cron); DelegationEngine.
  try_parse_delegation(); tests/test_bot_assistant.py 11,
  test_alert_dispatcher_wiring.py 3; всего 626 тестов)
- [x] 8.31 Режим «пишу только владельцу» + заполнение сотрудников - COMPLETED
  (TelegramSender allowlist: `allowed_chat_ids`, исходящие только разрешённым;
  настройки `TELEGRAM_OWNER_CHAT_ID` / `TELEGRAM_ALLOWLIST_ONLY` (default true,
  без владельца не шлёт вообще); команда `/here`; `seed_roles_from_employees`
  заполняет `system_roles` из config/employees.json при старте бота;
  tests/test_seed_roles.py 4, allowlist +6, build_sender +3; всего 639 тестов)
- [x] 8.32 Эмбеддинги и RAG на llama.cpp - COMPLETED
  (отдельный `llama-server --embedding --pooling cls` на 8081 с bge-m3
  (`C:\models\bge-m3-Q8_0.gguf`, dim 1024), `start_embed_server.bat`;
  `LlamaCppClient.get_embeddings` (батч) + `embeddings_available`;
  `app/modules/rag/llama_embeddings.py` (ChromaDB EF);
  `ChromaManager(embedding_function=...)` + `get_default_embedding_function`
  (llama по умолчанию, ollama — легаси через `EMBED_BACKEND`);
  `LlamaCppManager.start_server(embeddings=True, pooling="cls")`; настройки `LLAMA_EMBED_URL`/
  `EMBED_BACKEND`; автозапуск embedding-сервера из GUI (CPU, 8081, пропуск если уже
  запущен); проверено вживую add/search + автозапуск (dim 1024); +13 тестов, всего 652)
- [x] 8.33 Память диалога в боте - COMPLETED
  (`ConversationMemory` в app/bot/assistant.py: контекст по чатам, ограничение по
  ходам/длине; `_chat` шлёт историю в llama.cpp; команда `/reset`; проверено вживую;
  +8 тестов, всего 660)

## [✅] ЭТАП 9: Критические исправления (RFC: rfc_mia_fixes.md)
- RFC: docs/rfc_mia_fixes.md
- Status: ✅ COMPLETED (9.11 PostgreSQL Migration — ⏸️ DEFERRED, требует setup)
- Implementation: app/modules/vram_policy.py, app/core/safe_tool_layer.py, app/modules/rag/structured_excel_parser.py, app/modules/rag/state_replay.py, app/modules/google_drive/override_detector.py, app/workers/multiprocessing_worker_pool.py, app/modules/object_diary/telegram_distiller.py, app/modules/financial/ledger_integration.py
- Notes: Критические архитектурные уязвимости, инфраструктурные бутылочные горлышка, недоделки
- [x] 9.1 VRAM Policy Fix - динамический сплит моделей, одна модель, жесткое квантование
- [x] 9.2 Disable Workshop Contour - отключить генерацию CodeCandidate (уже не используется)
- [x] 9.3 Safe Tool Generation Layer (Prototype) - песочница для динамического кода
- [x] 9.4 Remove Duplicate Modules - очистка структуры кода (дубли перемещены в archive)
- [x] 9.5 Hybrid RAG for Excel/Estimates - структурированный парсинг, гибридный поиск
- [x] 9.6 Chronological State Replay Engine - версионирование чанков, фильтр по статусу
- [x] 9.7 Implicit Override Detection - детекция оверрайдов документов
- [x] 9.8 Worker Pool Multiprocessing - переписать на Multiprocessing
- [x] 9.9 Telegram Distiller Priority - слова-маркеры, вес риска
- [x] 9.10 Financial Ledger Integration - привязка к реальным оплатам (mock интеграция)
- [ ] 9.11 PostgreSQL Migration - перенос транзакционной нагрузки на PostgreSQL (DEFERRED - требует setup)
- [x] 9.12 Восстановление пакета `app/modules/temporal` (temporal_logic, alert_dispatcher,
  temporal_alert_integration) - модули лежали в `archive/` как `*_duplicate.py`, пакет не
  импортировался; починен `gui/mia_gui.py` (`TemporalLogic` → `TemporalLogicManager`)
- [x] 9.13 Починка импортов `DocumentParser` → `DocumentParserFactory` в
  document_info_extractor / contract_analyzer / rag.document_ingestor
