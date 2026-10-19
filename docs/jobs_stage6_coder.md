# Джобы для кодера - Этап 6: Интеграция GUI с runtime

## Job #34: Интеграция GUI с production Telegram/agent runtime
**Приоритет**: HIGH
**Статус**: COMPLETED (см. Todo.md Этап 6.1)
**Описание**: GUI сейчас делает только тестовые вызовы компонентов. Нужно интегрировать его с реальным production runtime (Telegram bot, agent loop, worker pool).

### Задачи:
1. **Изучить существующий production runtime**:
   - `mia/bot/main.py` - точка входа Telegram бота
   - `mia/assistant/service.py` - оркестрация ответа
   - `app/workers/worker_pool.py` - воркер пул
   - Понять структуру и зависимости

2. **Создать Runtime Manager**:
   - Файл: `app/runtime/manager.py`
   - Класс: `RuntimeManager`
   - Методы:
     - `start_telegram_bot()` - запуск бота как subprocess
     - `stop_telegram_bot()` - остановка бота
     - `start_worker_pool()` - запуск воркеров
     - `stop_worker_pool()` - остановка воркеров
     - `get_status()` - сбор статуса всех компонентов
   - Логирование в `mia_runtime.log`

3. **Интегрировать Runtime Manager в GUI**:
   - В `gui/mia_gui_redesigned.py`:
     - Импортировать `RuntimeManager`
     - Добавить в `__init__`: `self.runtime_manager = RuntimeManager()`
     - В вкладке "System Status" показать реальные статусы:
       - Telegram Bot: Running/Stopped/Error
       - Worker Pool: Running/Stopped/Error
       - LLM Server: Running/Stopped/Error
     - Кнопки: Start/Stop для каждого компонента

4. **Обработка процессов**:
   - Telegram бот запускать как subprocess с `subprocess.Popen`
   - Сохранять PID в runtime.json
   - При старте GUI проверять существующие процессы
   - При закрытии GUI корректно останавливать все процессы

5. **Логирование в GUI**:
   - Добавить вкладку "Runtime Logs"
   - Чтение `mia_runtime.log` в реальном времени
   - Автообновление каждые 2 секунды

### Выход:
- `app/runtime/manager.py` - Runtime Manager
- Обновлённый `gui/mia_gui_redesigned.py` с интеграцией
- Production runtime управляется из GUI

---

## Job #35: Полноценный start/stop/status/log интерфейс для всех компонентов
**Приоритет**: HIGH
**Статус**: COMPLETED (см. Todo.md Этап 6.2)
**Описание**: GUI должен показывать и управлять всеми компонентами системы: Telegram bot, Worker Pool, LLM Server, Doctor Observer, Audit Vector.

### Задачи:
1. **Создать Component Status Schema**:
   - Файл: `app/core/schemas.py`
   - Класс: `ComponentStatusSchema`
   - Поля:
     - `component_name`: str (telegram_bot, worker_pool, llm_server, doctor_observer, audit_vector)
     - `status`: str (running, stopped, error, starting, stopping)
     - `pid`: Optional[int]
     - `uptime`: Optional[float]
     - `last_heartbeat`: Optional[datetime]
     - `error_message`: Optional[str]

2. **Расширить Runtime Manager**:
   - Добавить компоненты:
     - `start_doctor_observer()` - запуск наблюдателя
     - `stop_doctor_observer()` - остановка наблюдателя
     - `start_audit_vector()` - запуск аудита
     - `stop_audit_vector()` - остановка аудита
   - Метод `get_all_statuses()` - возвращает List[ComponentStatusSchema]
   - Метод `start_all()` - запускает все компоненты по порядку
   - Метод `stop_all()` - останавливает все компоненты по порядку

3. **Обновить GUI вкладку "System Status"**:
   - Таблица с компонентами:
     - Component | Status | PID | Uptime | Actions
   - Кнопки:
     - Start Component
     - Stop Component
     - Restart Component
     - View Logs
   - Индикаторы:
     - 🟢 Running
     - 🔴 Stopped
     - 🟡 Error
     - ⚪ Starting/Stopping

4. **Добавить вкладку "Component Logs"**:
   - Dropdown: выбор компонента
   - ScrolledText: логи выбранного компонента
   - Автообновление каждые 2 секунды
   - Кнопки: Pause/Resume, Clear, Export

5. **Heartbeat система**:
   - Каждый компонент пишет heartbeat в SQLite каждые 30 секунд
   - Runtime Manager проверяет heartbeat и обновляет статус
   - Если heartbeat старше 60 секунд → статус Error

### Выход:
- `ComponentStatusSchema` в `app/core/schemas.py`
- Расширенный `RuntimeManager` в `app/runtime/manager.py`
- Обновлённый GUI с полным управлением компонентами
- Таблица компонентных статусов в SQLite

---

## Job #36: Натурально-языковое управление через Telegram для start/stop/status
**Приоритет**: MEDIUM
**Статус**: COMPLETED (см. Todo.md Этап 6.3)
**Описание**: Добавить команды для управления системой через Telegram на естественном языке.

### Задачи:
1. **Создать Command Handler**:
   - Файл: `mia/bot/handlers/commands_natural.py`
   - Функция: `handle_natural_command(message)`
   - Распознавание намерений:
     - "Мия, запусти бота" → start_telegram_bot
     - "Мия, останови бота" → stop_telegram_bot
     - "Мия, статус системы" → get_system_status
     - "Мия, запусти все" → start_all
     - "Мия, останови все" → stop_all

2. **Интегрировать с Intent Classifier**:
   - Использовать существующий `app/modules/object_diary/intent_classifier.py`
   - Добавить новые доменные намерения:
     - `SYSTEM_START` - запуск компонента
     - `SYSTEM_STOP` - остановка компонента
     - `SYSTEM_STATUS` - запрос статуса
     - `SYSTEM_RESTART` - перезапуск компонента

3. **Добавить RBAC проверку**:
   - Только авторитетные пользователи могут управлять системой
   - Проверка `is_authoritative` из `mia/core/employees.py`
   - Если не авторитетен → "У вас нет прав для управления системой"

4. **Форматирование ответов**:
   - Статус в виде таблицы:
     ```
     📊 Статус системы:
     🟢 Telegram Bot: Running (PID: 1234, Uptime: 2h 30m)
     🟢 Worker Pool: Running (4 workers active)
     🟢 LLM Server: Running (Qwen2.5-14B)
     🔴 Doctor Observer: Stopped
     🔴 Audit Vector: Stopped
     ```
   - Ответы на русском, как у Миа

5. **Логирование команд**:
   - Каждая команда управления логируется в SQLite
   - Записывается: кто, когда, какую команду выполнил
   - Таблица: `system_commands_log`

### Выход:
- `mia/bot/handlers/commands_natural.py` - обработчик NL команд
- Интеграция с Intent Classifier
- RBAC проверка для системных команд
- Логирование системных команд в SQLite

---

## Job #37: Обновить/удалить устаревшие ссылки на query_structured_db
**Приоритет**: LOW
**Статус**: COMPLETED (2026-10-19: проверено — `query_structured_db` отсутствует и в коде, и в актуальной документации; остались только в описании этой джобы и в `docs/archive/`. См. docs/changelog.md)
**Описание**: Найти и удалить/обновить все упоминания `query_structured_db` в RFC и документации, так как этот метод был заменён на безопасные semantic tools.

### Задачи:
1. **Поиск по документации**:
   - `grep -r "query_structured_db" docs/`
   - Найти все файлы с упоминаниями

2. **Анализ контекста**:
   - В каждом случае понять:
     - Это объяснение устаревшего подхода?
     - Это ссылка на существующий код?
     - Это нужно удалить или заменить?

3. **Замена/удаление**:
   - Удалить ссылки на устаревший метод
   - Заменить на упоминание безопасных semantic tools
   - Обновить RFC архитектуры
   - Обновить Todo.md

4. **Проверка кода**:
   - `grep -r "query_structured_db" app/`
   - Убедиться, что код не использует этот метод
   - Если использует → заменить на безопасный аналог

5. **Документация изменений**:
   - Создать запись в `docs/changelog.md`
   - Описать что было изменено и почему

### Выход:
- Обновлённая документация без устаревших ссылок
- Проверенный код без использования `query_structured_db`
- Changelog с описанием изменений

---

## Job #38: Модернизировать Pydantic схемы (class-based Config → ConfigDict)
**Приоритет**: MEDIUM
**Статус**: COMPLETED (2026-10-19: проверено — class-based `Config` в коде отсутствует, все схемы используют `model_config = ConfigDict(...)`; см. Todo.md 6.8/6.11)
**Описание**: Заменить устаревший синтаксис `class Config` на современный `model_config = ConfigDict(...)` во всех Pydantic схемах.

### Задачи:
1. **Найти все схемы с class-based Config**:
   - `grep -r "class Config" app/`
   - Список файлов для обновления

2. **Паттерн замены**:
   ```python
   # Было:
   class MySchema(BaseModel):
       field: str
       
       class Config:
           use_enum_values = True
           json_schema_extra = {"example": {...}}
   
   # Стало:
   class MySchema(BaseModel):
       field: str
       
       model_config = ConfigDict(
           use_enum_values=True,
           json_schema_extra={"example": {...}}
       )
   ```

3. **Обновить файлы**:
   - `app/core/schemas.py`
   - `app/modules/object_diary/*.py`
   - `app/modules/storage/*.py`
   - Все остальные Pydantic схемы

4. **Проверка типов**:
   - Запустить `pytest tests/test_schemas.py`
   - Убедиться, что все тесты проходят
   - Проверить валидацию данных

5. **Проверка runtime**:
   - Запустить GUI
   - Убедиться, что схемы работают корректно
   - Проверить создание/чтение из SQLite

### Выход:
- Все Pydantic схемы с современным синтаксисом
- Пройденные тесты
- Проверенный runtime

---

## Job #39: Обзор аудита (воспроизводимость, происхождение, одобрения, идемпотентность)
**Приоритет**: MEDIUM
**Статус**: COMPLETED (см. Todo.md Этап 6.9)
**Описание**: Создать систему аудита для отслеживания происхождения изменений, одобрений и идемпотентности операций.

### Задачи:
1. **Создать Audit Log Schema**:
   - Файл: `app/core/schemas.py`
   - Класс: `AuditLogSchema`
   - Поля:
     - `audit_id`: Optional[int]
     - `timestamp`: datetime
     - `actor`: str (user_id или "system")
     - `action`: str (create, update, delete, approve, reject)
     - `entity_type`: str (object_diary, document, contract, etc.)
     - `entity_id`: str
     - `old_value`: Optional[Dict[str, Any]]
     - `new_value`: Optional[Dict[str, Any]]
     - `approval_chain`: List[str] - кто одобрил
     - `origin`: str (manual, llm_generated, automated)
     - `trace_id`: str - для связывания операций

2. **Создать Audit Logger**:
   - Файл: `app/core/audit_logger.py`
   - Класс: `AuditLogger`
   - Методы:
     - `log_change(actor, action, entity_type, entity_id, old_value, new_value, origin)`
     - `log_approval(actor, entity_type, entity_id, decision)`
     - `get_history(entity_type, entity_id)` - история изменений
     - `get_trace(trace_id)` - все операции в трассировке

3. **Интегрировать в существующие модули**:
   - `app/modules/object_diary/diary_manager.py` - логировать изменения diary
   - `app/modules/storage/database.py` - логировать записи в БД
   - `app/modules/google_drive/document_processor.py` - логировать обработку документов

4. **Добавить в GUI**:
   - Вкладка "Audit Log"
   - Фильтры: по типу сущности, по actor, по дате
   - Таблица: Timestamp | Actor | Action | Entity | Changes
   - Детали изменения: показать old_value vs new_value

5. **Идемпотентность**:
   - Каждая операция генерирует уникальный trace_id
   - Если операция с тем же trace_id уже была → пропустить
   - Предотвращение дублирования операций

### Выход:
- `AuditLogSchema` в `app/core/schemas.py`
- `AuditLogger` в `app/core/audit_logger.py`
- Интеграция в существующие модули
- Вкладка "Audit Log" в GUI
- Система идемпотентности через trace_id

---

## Порядок выполнения:

1. **Job #34** - Интеграция GUI с Telegram runtime (основа для всего остального)
2. **Job #35** - Полноценный интерфейс управления компонентами
3. **Job #36** - NL управление через Telegram (после #35)
4. **Job #38** - Модернизация Pydantic схем (можно параллельно)
5. **Job #37** - Удаление устаревших ссылок (можно параллельно)
6. **Job #39** - Обзор аудита (можно в конце)

---

## Примечания для кодера:

- Использовать существующую архитектуру (см. `architecture.md`)
- Следовать RFC v1.9 для Object Diary
- Соблюдать трёхконтурную архитектуру (Companion, Studio, Workshop)
- Добавлять type hints и docstrings
- Писать тесты для новых модулей
- Не нарушать существующие тесты (pytest должен проходить)
