# RFC: Object Diary (Дневник Объекта)

## Версия RFC
- **Версия**: 1.10
- **Статус**: ✅ COMPLETED (2026-10-19: Jobs #1–#33 реализованы, модули в `app/modules/object_diary/`; см. Todo.md 8.7–8.16)
- **Дата создания**: 2026-09-20
- **Дата обновления**: 2026-10-19
- **Автор**: Devin AI Assistant
- **Область**: Project Ledger System
- **Рецензенты**: Google AI (архитектурные решения v8 - Живая Онтология Девиаций) + Гигиена проекта (RFC-032)
- **Стандарты надежности**: Трехконтурная архитектура, CodeCandidate, Subprocess-Smoke, Hash-Bound Admission

## Аннотация
Этот RFC описывает систему Дневников объектов для централизованного хранения всей информации о строительных объектах, включая договоры, документы, финансовые данные и временные шкалы событий. Система должна автоматически связывать документы с объектами, отслеживать переход от коммерческих предложений к договорам, и обеспечивать умный поиск информации внутри и между объектами.

## Методологическая основа: Lean Construction + Event-Driven Architecture

Для работы в стохастической строительной среде Mia базируется на методологии Lean Construction (Бережливое строительство) и Last Planner System (Система Последнего Планировщика), скрещенной с событийно-ориентированной архитектурой (Event-Driven Architecture).

### Сеть Условий и Ограничений (Constraint Management)
Вместо жесткой цепи «Договор ➔ ТУ ➔ Проект ➔ ОАТИ ➔ Земляные работы», Mia строит Сеть Условий и Ограничений. Объект — это бассейн событий и сито ограничений, которые эти события должны пройти. Каждому целевому действию важно только одно: сняты ли все блокирующие ограничения на сегодняшний день?

### Intent Classifier вместо жестких скриптов
Для анализа чатов используется Паттерн «Анализатор Намерений на Базовых Концептах» (Intent Classifier). LLM классифицирует действие в терминах строительного домена, а детерминированный Python-код страхует модель от ошибок.

### Кумулятивный риск (Health Score)
Mia вычисляет Индекс Здоровья Объекта (Health Score) — кумулятивный риск от совокупности мелких событий. Несколько факторов (перенос КП, рост цены кабеля, отсутствие штампа) вместе переводят объект в статус «Красная зона / Риск дефолта».

## Предпосылки

### Текущее состояние
- Реализована OAuth аутентификация для Google Drive
- Выполнено сканирование папки "5_Стройка" (108 строительных объектов обнаружено)
- Выполнено сканирование папки "Договоры" (1710 папок, 6295 файлов)
- Реализованы парсеры для PDF, Word, Excel
- Созданы basic project ledgers для обнаруженных объектов

### Проблемы
- Нет централизованной системы хранения информации по объектам
- Нет автоматического связывания документов с объектами
- Нет отслеживания перехода КП → Договор
- Нет поиска информации внутри и между объектами
- Нет структуры для хранения иерархии договоров (заказчик → подрядчики)

## Цели

### Основные цели
1. Создать систему Дневников объектов для каждого строительного объекта
2. Реализовать автоматический мониторинг папки "Договоры" (раз в день)
3. Связывать документы с объектами через анализ текста и контекста
4. Отслеживать переход КП → Договор как один объект
5. Обеспечить поиск информации внутри объекта и параллели между объектами

### Вторичные цели
1. Создать особую ветку для справочных документов (разрешения МПТЦ, СНИП)
2. Поддерживать версию документов (последний отменяет предыдущий)
3. Обеспечить расширяемую структуру полей
4. Интегрировать с RAG для умного поиска

## Нефункциональные требования

### Производительность
- Мониторинг папки "Договоры" раз в день
- Обработка новых документов в течение разумного времени
- Поиск по объектам и между объектами должен быть быстрым

### Надежность
- Договоры неизменны, доп. соглашения = новые документы
- Сохранять информацию о предыдущих версиях документов
- Автоматическое обнаружение ошибок связывания

### Масштабируемость
- Поддержка большого количества объектов (108+ обнаружено)
- Поддержка большого количества документов (6295+ в папке "Договоры")
- Расширяемая структура полей для ledger'ов

## Архитектура

### Трехконтурная Архитектура Системы (по RFC-032)

Внутренние модули Mia разбиты на три изолированных контура для обеспечения надежности и безопасности:

#### Контур 1: Companion (Контур диалога)
- **Назначение**: Telegram-клиент, чтение состояний, регистрация запросов
- **Разрешенные операции**: Чтение из БД, отправка уведомлений, обработка пользовательских команд
- **Запрещенные операции**: Прямое изменение БД, генерация кода, выполнение SQL-запросов на запись
- **Модули**: telegram_handlers, telegram_distiller, alert_dispatcher (только рассылка)
- **Безопасность**: Read-only доступ к SQLite, запрещен importlib.import_module

#### Контур 2: Studio (Контур детерминированных рецептов)
- **Назначение**: Выполнение жесткого Python/SQL-кода, NetworkX, SQL-запросы к деньгам, базовые парсеры
- **Разрешенные операции**: Детерминированная логика, SQL-запросы на чтение, NetworkX анализ
- **Логика**: Жестко зафиксирована, не подлежит генерации слабыми моделями
- **Модули**: diary_manager, constraint_manager, health_score_engine, temporal_logic, document_linker
- **Безопасность**: Все операции проверены, CodeCandidate не допускается

#### Контур 3: Workshop (Контур исследований Devin)
- **Назначение**: Изолированная зона для генерации новых промптов, кодовых обработчиков и "линз внимания"
- **Разрешенные операции**: Генерация промптов, создание CodeCandidate, кластеризация уроков
- **Источники**: Таблица expert_lessons, пользовательская обратная связь
- **Модули**: expert_teacher, accuracy_contour (только аналитика), intent_classifier (генерация)
- **Безопасность**: Генерация только в sandbox/candidates/, изоляция через Subprocess-Smoke

### Основные компоненты

#### 1. Object Diary Manager
```
app/modules/object_diary/
├── diary_manager.py          # Основной менеджер дневников (CRUD, таймлайн)
├── document_linker.py       # Отдельный модуль связывания документов (изолированный пайплайн)
├── contract_analyzer.py     # Анализ текста договоров с цитированием
├── pre_object_tracker.py    # Отслеживание КП → Договор
├── knowledge_graph.py       # Граф связей между объектами (SQLite + object_edges)
├── inbox_manager.py         # Human-in-the-loop для неоднозначных случаев
├── accuracy_contour.py      # Контур точности: тройной аудит дедлайнов
├── role_router.py           # Адресный Human-in-the-loop: умная маршрутизация
├── virtual_documents.py     # Учет фантомных (отсутствующих) документов
├── telegram_distiller.py    # Агрегация хаоса: слияние документов и Telegram-каналов
├── temporal_logic.py        # Контур темпоральной логики (Absolute Time Injection)
├── alert_dispatcher.py      # Диспетчер алертов (напоминания и тревоги)
├── delegation_engine.py     # Паттерн «Спроси у Светы» (динамическая делегация)
├── constraint_manager.py    # Сеть Условий и Ограничений (Lean Construction)
├── intent_classifier.py     # Анализатор Намерений на Базовых Концептах
├── negative_event_trigger.py # Триггеры на «Молчание» (Negative Event Trigger)
├── health_score_engine.py   # Кумулятивный риск (Health Score)
└── expert_teacher.py        # Модуль интерактивного обучения: Живая Онтология Девиаций
```

#### 2. Структура Дневника объекта
```python
class ObjectDiarySchema(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    diary_id: Optional[int] = None
    object_name: str
    object_id: str  # Google Drive folder ID
    
    # Информация о заказчике
    customer: Optional[str] = None
    customer_company: Optional[str] = None
    
    # Договорная информация
    contract_date: Optional[datetime] = None
    contract_amount: Optional[float] = None
    contract_number: Optional[str] = None
    
    # Субподрядчики
    subcontractors: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Связи с другими договорами
    parent_contract_id: Optional[str] = None
    sub_contracts: List[str] = Field(default_factory=list)
    
    # Префаза - КП
    has_proposal: bool = False
    proposal_date: Optional[datetime] = None
    proposal_amount: Optional[float] = None
    converted_to_contract: bool = False
    
    # Расширяемые поля
    custom_fields: Dict[str, Any] = Field(default_factory=dict)
    
    # Временная шкала
    events: List[DiaryEventSchema] = Field(default_factory=list)
    
    # Метаданные для RAG
    rag_metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Метаданные
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
```

#### 3. Схема события в дневнике
```python
class DiaryEventSchema(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    event_id: Optional[int] = None
    event_type: str  # contract_created, proposal_sent, document_added, etc.
    event_timestamp: datetime
    entity_type: str  # document, contract, payment, etc.
    entity_id: str
    summary: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Версионирование
    overrides_event_id: Optional[int] = None
    is_current: bool = True
    
    # Защита от галлюцинаций - цитирование
    citation_text: Optional[str] = None  # Строка из текста, на основе которой принято решение
    citation_page: Optional[int] = None  # Номер страницы в документе
    citation_bbox: Optional[Dict[str, float]] = None  # Координаты для подсветки (x0, y0, x1, y1)
    citation_confidence: Optional[float] = None  # Уверенность модели (0-1)
    
    # Статус связывания
    requires_verification: bool = False  # Требует ручной проверки
    verification_status: Optional[str] = None  # AUTO_VERIFIED, HUMAN_VERIFIED, CONFLICT

    # Темпоральный контекст
    temporal_context: Optional[Dict[str, Any]] = None  # Абсолютное время, относительные переводы
```

#### 4. Схема темпорального контекста
```python
class TemporalContextSchema(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    current_absolute_time: datetime
    current_day_of_week: str
    relative_translation_map: Dict[str, str] = Field(default_factory=dict)
    # Пример: {"Сегодня": "2026-09-20", "Завтра": "2026-09-21", "Вчера": "2026-09-19"}
```

#### 5. Схема делегирования
```python
class DelegationRequestSchema(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    request_id: Optional[int] = None
    requester_id: str  # Кто делегирует
    target_name: str  # Кого делегируем (например, "Света")
    question_context: str  # Контекст вопроса
    object_id: str  # Объект, к которому относится вопрос
    created_at: datetime = Field(default_factory=datetime.now)
    status: str = "PENDING"  # PENDING, DELEGATED, ANSWERED
```

#### 6. Схема делегированного вопроса
```python
class DelegatedQuestionSchema(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    question_id: Optional[int] = None
    original_request_id: int
    assigned_user_id: str  # Кому делегирован
    assigned_user_role: str  # PURCHASING, LEGAL, etc.
    communication_channel: str  # PRIVATE (ЛС) or PUBLIC (общий чат)
    message_sent: bool = False
    answer_received: bool = False
    answer_text: Optional[str] = None
    answer_timestamp: Optional[datetime] = None
    deadline_for_reply: Optional[datetime] = None  # Дедлайн для ответа
    reminder_count: int = 0  # Количество напоминаний
    escalation_status: str = "NONE"  # NONE, REMINDED, ESCALATED
    escalated_to_user_id: Optional[str] = None  # Кому эскалирован (если не ответили)
    escalation_timestamp: Optional[datetime] = None
```

#### 7. Схема намерения (Intent)
```python
class IntentSchema(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    intent_id: Optional[int] = None
    domain_intent: str  # MOVE_MATERIAL, SCHEDULE_CHANGE, APPROVAL_REQUEST, etc.
    material_concept: Optional[str] = None  # well_rings_or_chambers, cable, etc.
    source_location_raw: Optional[str] = None
    target_location_raw: Optional[str] = None
    confidence: float
    source_message_id: str  # ID сообщения в Telegram
    extracted_at: datetime = Field(default_factory=datetime.now)
```

#### 8. Схема ограничения (Constraint)
```python
class ConstraintSchema(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    constraint_id: Optional[int] = None
    object_id: str
    constraint_type: str  # TELCO_APPROVAL, STAMP_OPS, OATI_NOTIFICATION, etc.
    constraint_name: str
    description: str
    required_for_actions: List[str] = Field(default_factory=list)  # Какие действия требуют этого ограничения
    status: str = "NOT_SATISFIED"  # NOT_SATISFIED, SATISFIED, WAIVED
    satisfied_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    source_document_id: Optional[str] = None
    severity_level: str = "MAJOR"  # CRITICAL, MAJOR, MINOR - цена нарушения ограничений
    bypass_strict_rule: bool = False  # Флаг "Пакта о помиловании" от Метода 3
    bypass_reason: Optional[str] = None  # Причина обхода строгого правила (устное согласование)
    bypass_expiry: Optional[datetime] = None  # Когда истекает действие обхода
```

#### 9. Схема Health Score
```python
class HealthScoreSchema(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    score_id: Optional[int] = None
    object_id: str
    score: float  # 0-100
    zone: str  # GREEN, YELLOW, RED
    calculated_at: datetime = Field(default_factory=datetime.now)
    contributing_events: List[Dict[str, Any]] = Field(default_factory=list)
    risk_factors: List[str] = Field(default_factory=list)  # Описание факторов риска
```

#### 10. Схема экспертного урока (ExpertLesson)
```python
class ExpertLessonSchema(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    lesson_id: Optional[int] = None
    doc_category: str  # TECHNICAL_PROJECT, SPECIFICATION, ESTIMATE
    
    # Смысловые якоря (Теги интерфейса: "Ростелеком", "Канализация КК", "МГГТ")
    context_tags: List[str] = Field(default_factory=list)
    
    # Текстовый слепок и вектор страницы для RAG
    raw_page_text: str
    anchor_text_embedding_id: str
    
    # Суть урока и комментарий инженера
    expert_commentary: str  # Пример: "Ростелеком требует кабель с пометкой HF"
    
    # Граница применимости девиации (Выводится Девином автоматически)
    applicability_scope: Dict[str, Any] = Field(default_factory=dict)
    # Пример: {"customer": "Ростелеком", "work_type": "канализация", "component": "кабель"}
    
    created_at: datetime = Field(default_factory=datetime.now)
    verified_by_human: bool = False
```

#### 4. Классификация документов
```python
class DocumentCategory(str, Enum):
    CONTRACT = "contract"          # Договор
    ADDENDUM = "addendum"          # Доп. соглашение
    PROPOSAL = "proposal"          # КП
    FINANCIAL = "financial"        # Финансовые документы
    TECHNICAL = "technical"        # Технические документы
    LEGAL = "legal"                # Юридические документы
    REFERENCE = "reference"        # Справочные документы (СНИП, разрешения)
    OTHER = "other"                # Другое
```

### Пайплайн обработки

### Паттерн "CodeCandidate" для защиты ядра

Любой код, SQL-запрос или промпт, сгенерированный слабой моделью (8B) в системе, получает статус CodeCandidate:

```python
class CodeCandidateSchema(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    candidate_id: Optional[int] = None
    candidate_type: str  # CODE, SQL_QUERY, PROMPT
    source_model: str  # gemma-3-12b, qwen-3-coder-14b
    generated_code: str
    target_module: str  # diary_manager, constraint_manager, etc.
    source_context: str  # Контекст генерации (какой запрос пользователя)
    status: str = "PENDING"  # PENDING, APPROVED, REJECTED, BLOCKED
    sha256_hash: str  # Хэш для допуска
    smoke_test_result: Optional[str] = None  # SMOKE_OK, SMOKE_FAILED
    created_at: datetime = Field(default_factory=datetime.now)
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None  # "devin" или архитектор
```

**Правила хранения:**
- CodeCandidate сохраняется строго в директорию `sandbox/candidates/`
- Прямая запись в живые модули ядра `app/modules/` ЗАПРЕЩЕНА
- Допуск в основную систему только после прохождения Subprocess-Smoke и Hash-Bound Admission

### Изоляция Исполнения (Subprocess-Smoke)

Запретить in-process импорт (`importlib.import_module`) непроверенных кандидатов кода в основной процесс Mia:

```python
class AdmissionGate:
    def test_candidate(self, candidate: CodeCandidateSchema) -> AdmissionResult
    def run_subprocess_smoke(self, candidate: CodeCandidateSchema) -> SmokeTestResult
    def validate_hash_integrity(self, candidate: CodeCandidateSchema) -> bool
```

**Процесс допуска:**
1. Генерация CodeCandidate → сохранение в `sandbox/candidates/`
2. Запуск независимого изолированного `subprocess` для тестирования
3. Проверка `Exit Code == 0` и маркера `SMOKE_OK`
4. Подписание SHA-256 хэшем (Hash-Bound Admission)
5. Допуск в контур Studio только при успешном прохождении всех проверок

### Допуск по Хэшу (Hash-Bound Admission)

Каждое допущенное правило проверки, промпт или SQL-шаблон подписывается SHA-256 хэшем:

```python
class HashBoundSchema(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    hash_id: Optional[int] = None
    resource_type: str  # PROMPT, SQL_TEMPLATE, VALIDATION_RULE
    resource_path: str  # Путь к файлу в системе
    sha256_hash: str
    resource_content: str
    status: str = "ACTIVE"  # ACTIVE, BLOCKED, REVOKED
    created_at: datetime = Field(default_factory=datetime.now)
    last_verified: datetime = Field(default_factory=datetime.now)
    verified_by: str  # "devin" или архитектор
```

**Правила защиты:**
- Любое несанкционированное изменение файла слабой моделью аннулирует хэш
- Модуль переводится в статус `BLOCKED` до ручной проверки архитектором (Devin)
- Проверка хэша происходит при каждом запуске системы

### Мониторинг папки "Договоры"
```
Раз в день:
1. Сканировать папку "Договоры"
2. Найти новые документы (по ID, дате изменения)
3. Классифицировать каждый документ (договор, доп. соглашение, КП)
4. Анализировать текст для определения объекта
5. Связать документ с объектом или создать новый дневник
```

#### 2. Связывание документов с объектами
```
Для каждого документа:
1. Анализ названия файла (адреса, объекты)
2. Анализ содержимого (упоминания объектов, заказчиков)
3. Анализ контекста (путь в Google Drive)
4. Если найдено однозначное совпадение → связать
5. Если нет совпадения → создать новый дневник (если КП) или спросить пользователя
6. Если несколько совпадений → спросить пользователя
```

#### 3. Отслеживание КП → Договор
```
1. При обнаружении КП создать пре-объект
2. При обнаружении договора на тот же объект → преобразовать в объект
3. Сохранить историю перехода (дата КП, дата договора, сумма КП, сумма договора)
4. Отметить конверсию сделки
```

#### 4. Иерархия договоров
```
1. Анализ текста договора для определения заказчика
2. Поиск связанных договоров с подрядчиками
3. Создание связей parent_contract_id ↔ sub_contracts
4. Пример: СЭС (заказчик) → ВэллДан (генподрядчик) → ГНБ (подрядчик)
```

#### 5. Справочная ветка
```
1. Определение справочных документов (разрешения МПТЦ, СНИП)
2. Хранение в основной таблице документов с object_id = "GLOBAL_REFERENCE"
3. Не выделять в отдельную таблицу - та же текстовая структура для RAG
4. Специальный системный ID объекта для подмешивания в поиск
5. Подмешивание при необходимости нормативной базы в контекст
```

#### 6. Human-in-the-loop для ошибок связывания
```
1. Агент никогда не молча принимает сомнительные решения
2. Динамический двухуровневый порог: 0.90 и 0.70
3. Confidence >= 0.90: Полностью автоматическое связывание (детерминированное совпадение ИНН/ОГРН, точный адрес)
4. 0.70 <= Confidence < 0.90: Связывание с флагом requires_verification=True, отправка в фоновый аудит
5. Confidence < 0.70: Безусловно падает в pending_links (Inbox)
6. Статус: AWAITING_HUMAN_REVIEW
7. Интерактивная карточка в GUI/Telegram:
   "Не могу привязать Договор №12. Обнаружено 2 похожих объекта:
    Объект А и Объект Б. Выберите правильный или создайте новый"
8. Таблица pending_links для отложенных решений
```

#### 7. Контур точности: Тройной перекрестный аудит дедлайнов и показателей
```
Архитектура независимых контуров для точности на RTX 5060 16Gb:

Метод 1: Детерминированный Граф Зависимостей (NetworkX)
- Жесткий код на Python-библиотеке NetworkX
- Описывает неизменные правила строительного ГОСТа и регламентов
- Пример правила: Уведомление ОАТИ ➔ требует ➔ Штамп ОПС МГГТ в проекте
- Результат: Чистая математика, без LLM-мышления
- Если нет штампа ОПС МГГТ → дедлайна ОАТИ статус БЛОКИРОВАН
- "Пакт о помиловании": Метод 3 может наложить временный флаг BYPASS_STRICT_RULE, если с 100% уверенностью извлечен факт устного согласования

Метод 2: Критический RAG по Спецификациям (Ollama 8B - mistral:7b-instruct-v0.3)
- Изолированное сравнение сущностей: Смета/КП ↔ Накладные/Акты ↔ Текущий таймлайн
- Находит аномалии во времени и деньгах
- Пример: КП 2024 года кабель 100 руб, накладная 2026 года кабель 120 руб → рост 20%
- Результат: Аномалии во времени и финансах

Метод 3: Анализатор Временных Сдвигов (Ollama 14B - qwen2.5:14b-instruct-q4_K_M)
- Читает переписку из Telegram-каналов объектов
- Сопоставляет с официальными документами
- Ловит неформальные дедлайны и перемещения
- Пример: Прораб сказал "везем колодец", но перемещение ТМЦ не оформлено
- Результат: Алерт о несоответствии фактов
- "Пакт о помиловании": Может наложить BYPASS_STRICT_RULE на детерминированные проверки Метода 1

Консенсус-Арбитр:
- Специальный промпт собирает выводы трех методов
- Если Метод 1 говорит "нельзя копать", а Метод 3 видит "мы начали копать"
- Mia бьет в набат: Критическое нарушение регламента
- Если Метод 3 наложил BYPASS_STRICT_RULE → снижение критичности проверки Метода 1
```

#### 7. Стратегия версионирования документов
```
1. Сущность Event (событие) - правильный выбор для версионирования
2. Не "последний отменяет предыдущий", а частичное изменение
3. Пример: Доп. соглашение №2 отменяет только пункт 3.1 Договора
4. RAG-поиск должен отдавать весь пакет:
   Договор + все Допы к нему
5. Агент формирует финальный ответ на основе актуальной цепочки изменений
6. Визуализация diff между версиями в GUI
```

#### 8. Учет фантомных (отсутствующих) документов - Shadow Document pattern
```
1. Система оперирует понятием "Жизненный цикл Объекта"
2. Для каждого типа объекта создается детерминированный чек-лист обязательных документов
3. Паттерн "Shadow Document" (Теневой документ):
   - Если документа физически нет в Google Drive → создается запись в virtual_documents
   - Статус: MISSING
   - Дедлайн: Дата_Договора + 14 дней (пример)
4. Поиск RAG:
   - ChromaDB → реальные чанки
   - SQLite → список MISSING документов
5. Пример ответа:
   "Найдено 3 акта. Ожидаются (но отсутствуют):
    Акт скрытых работ по проколу №2 (просрочен на 5 дней)"
```

#### 9. Адресный Human-in-the-loop: Умная маршрутизация вопросов
```
1. Матрица компетенций контрагентов/ролей в SQLite (system_roles)
2. Таблица system_roles:
   - user_id: Telegram ID / User ID
   - role: LEGAL, PROCTOR (Прораб), PURCHASING (Снабженец), PROJECT_ENG (Проектировщик)
   - object_id: ID объекта (или GLOBAL)
3. Логика маршрутизации:
   - Проблема: Истекает ТУ Ростелекома (юридическо-технический документ)
   - Действие: Запрос Юристу или ГИПу, закрепленному за объектом
   - Проблема: Перевозка колодца ККСр-3 на Профсоюзную (логистика и материалы)
   - Действие: Пуш в Telegram Прорабу Профсоюзной и Снабленцу
   - Пример: "Иван, подтвердите приемку колодца ККСр-3, уехавшего с Судакова. Да/Нет"
```

#### 10. Агрегация хаоса: Слияние документов и Telegram-каналов
```
1. Telegram-чаты — главный источник правды, но 90% флуда
2. Помещать весь чат в RAG нельзя — ChromaDB забьется мусором
3. Паттерн "Event Distiller" (Дистиллятор Событий):
   - Telegram-бот слушает чат конкретного объекта (связан по object_id)
   - Каждое сообщение проходит через быструю локальную фильтрацию (regex на ключевые слова)
   - Ключевые слова: кабель, колодец, привезли, ОАТИ, штамп, подписали
4. Обработка через LLM:
   - Раз в час или по триггеру запускается mistral:7b на пачку отфильтрованных сообщений
   - Промпт: "Выдели из этого флуда только строительные факты, изменения сроков или перемещения ТМЦ"
   - Формат: Дата | Факт | Сущность
5. Дистиллированный лог пишется в diary_events как событие типа CHAT_LOG
6. Векторизация: В ChromaDB уходят только дистиллированные факты, а не весь чат
7. ЗАМЕЧАНИЕ ПОЛЬЗОВАТЕЛЯ: Скриптовать анализ разговоров не будем - пропускаем через логику LLM для summary написанного
```

#### 11. Контур темпоральной логики (Absolute Time Injection)
```
1. Паттерн "Absolute Time Injection" (Инъекция абсолютного времени)
2. LLM запрещено угадывать время - работает в связке с системными часами
3. Пример мета-контекста для модели:
   [SYSTEM CONTEXT]
   Current Absolute Time: 2026-09-20 17:06:00
   Current Day of Week: Sunday
   Relative Translation Map:
   - "Сегодня" = 2026-09-20
   - "Завтра" = 2026-09-21
   - "Вчера" = 2026-09-19
   - "Позавчера" = 2026-09-18
   [END SYSTEM CONTEXT]
4. Обработка задачи "Напомнить завтра":
   - LLM (Mistral 7B) парсит фразу → JSON: {"intent": "SET_REMINDER", "relative_time": "tomorrow", "task": "..."}
   - Бэкенд берет текущую дату (2026-09-20) и математически прибавляет +1 день
   - В cron_tasks пишется строка с фиксированной датой: '2026-09-21 09:00:00'
5. Корректная интерпретация относительного времени из чатов ("напомни завтра", "позавчера увезли колодец")
```

#### 12. Проактивность в рамках лимитов: Напоминания и Тревоги
```
1. Диспетчер Алертов (Scheduler) на базе APScheduler
2. Регулярные Напоминания (раз в день, 10:00):
   - Скрипт собирает все задачи на сегодня из SQLite
   - Упаковывает в одно красивое сообщение
   - Шлет пользователю
3. Критические Тревоги (раз в день, 16:00):
   - Контур Тройного Аудита прогоняет данные объектов
   - Проверка просроченных ТУ Ростелекома, отсутствие штампов при начатых работах
   - Все критические несоответствия → отчет "🚨 КРИТИЧЕСКИЕ СБОИ СИСТЕМЫ"
4. Рабочее время: 9:00 - 18:00 (защита от спама)
```

#### 13. Паттерн «Спроси у Светы» (Динамическая делегация)
```
1. Граф ролей в SQLite (system_roles) + контекстный парсинг имен
2. Логика работы цепочки переадресации:
   - Пользователь: "Спроси у Светы"
   - Mia ищет "Света" в таблице контактов
   - Шаг 1 (Поиск сущности): Парсит имя, сопоставляет с system_roles (Sveta = PURCHASING)
   - Шаг 2 (Выбор канала связи):
     * Если у Светы запущен бот → пишет в ЛС
     * Если нет → пишет в общий чат проекта с тегом @Света
3. Пример:
   - Контекст: "Материалы для НСС6 закуплены с удорожанием на 20%, кто согласовал?"
   - Ответ пользователю: "Спроси у Светы"
   - Mia Свете: "Привет, Света! Денис просил уточнить по объекту Судакова (НСС6): Материалы закуплены с удорожанием на 20%, кто согласовал?"
```

#### 14. Обработка слепых зон делегации
```
1. Проблема «Света ответила в чате, но не мне» (Перехват ответа):
   - Таблица delegated_questions со статусом AWAITING_REPLY
   - Mistral:7b парсит сообщение Светы → ответ на вопрос или мем?
   - Если ответ → фиксирует в Дневнике, шлет уведомление пользователю
2. Многозначность имен («У нас три Светы»):
   - Если несколько совпадений → Human-in-the-loop в контексте беседы
   - Пример: "Денис, какую Свету иметь в виду? Свету из закупок (Судакова) или Свету-юриста?"
   - Инлайн-кнопки выбора
3. Изменение дедлайнов «задним числом»:
   - Статус дедлайна: PROLONGED_BY_CHAT (Продлено на основании обсуждения)
   - Если в чате зафиксирован факт устной договоренности → снижает критичность алерта до желтого
   - Защита от ложных алертов при несоответствии официальных и устных сроков
4. Проблема «Зависшего вопроса» (Эскалация):
   - Поля deadline_for_reply и reminder_count в DelegatedQuestionSchema
   - Если через 4 часа (рабочее время) статус PENDING → мягкое напоминание
   - Если ответа нет сутки → эскалация пользователю с пометкой: "Денис, Света не ответила в чате Судакова на вопрос по удорожанию НСС6 за 24 часа"
   - escalation_status: NONE → REMINDED → ESCALATED
   - escalated_to_user_id: кому эскалирован, escalation_timestamp: когда
```

#### 15. Lean Construction: Сеть Условий и Ограничений
```
1. Методологическая основа: Lean Construction + Last Planner System
2. Вместо жесткой цепи «Договор ➔ ТУ ➔ Проект ➔ ОАТИ ➔ Земляные работы»
3. Объект = бассейн событий + сито ограничений
4. Каждому целевому действию важно: сняты ли все блокирующие ограничения на сегодняшний день?
5. Пример проверки ограничений для «Земляные работы»:
   - ТУ выданы? (Да, но до конца 2 недели) ✅
   - Штамп ОПС есть? (Нет) ❌ ➔ Действие заблокировано, Mia бьет тревогу
6. Сеть Условий и Ограничений в SQLite:
   - Таблица constraints (ограничения: ТУ, штампы, разрешения)
   - Таблица constraint_dependencies (зависимости ограничений)
   - Таблица constraint_status (статус снятия ограничений)
```

#### 16. Intent Classifier вместо жестких скриптов
```
1. Паттерн «Анализатор Намерений на Базовых Концептах» (Intent Classifier)
2. Не жесткие скрипты на ключевых словах («привезли колодец» vs «бочка на Профсоюзной»)
3. LLM классифицирует действие в терминах строительного домена (JSON режим)
4. Пример сообщения: "Короче, кольца ККС для Профсоюзной скинули на Судакова, Ден в курсе."
5. LLM возвращает JSON:
   {
     "domain_intent": "MOVE_MATERIAL",
     "material_concept": "well_rings_or_chambers",
     "source_location_raw": "Профсоюзная",
     "target_location_raw": "Судакова",
     "confidence": 0.92
   }
6. Детерминированный Python-код страхует модель:
   - target_location_raw ("Судакова") → нечеткий поиск по базе 108 объектов
   - Если объект найден → привязка сущности к object_id
   - Проверка по технологии: нужны ли кольца ККС на этом этапе?
   - Если нет → мягкий алерт: "В чате пишут, что на Судакова привезли кольца ККС, но по плану они там не значатся. Проверить?"
7. Не галлюцинирует, потому что LLM — переводчик с «прорабского» на «системный», а не аналитик фактов
```

#### 17. Триггеры на «Молчание» (Negative Event Trigger)
```
1. Большинство систем реагируют на то, что написано
2. На стройке критично то, что забыто (отсутствие события)
3. Пример: Уведомление ОАТИ нужно получить за несколько дней до земляных работ
4. Если плановый старт земляных работ через 5 дней, а события «Получено уведомление ОАТИ» нет
5. Mia генерирует алерт на основе отсутствия события (Negative Event Trigger)
6. Таблица negative_events_triggers:
   - trigger_id, object_id, expected_event_type, deadline_date, severity
7. Ежедневная проверка: если дата подошла, а события нет → алерт
```

#### 18. Кумулятивный риск (Health Score)
```
1. Стройка умирает не при плохом событии, а при кумуляции мелких сбоев
2. Индекс Здоровья Объекта (Health Score) — кумулятивный риск
3. Пример кумуляции:
   - Перенос КП на неделю — не страшно
   - Рост цены кабеля на 20% — неприятно, но терпимо
   - Отсутствие штампа ОПС — бывает
   - Все три вместе → «Красная зона / Риск дефолта»
4. Health Score вычисляется ежедневно по формуле:
   - Каждое событие имеет вес (severity: LOW, MEDIUM, HIGH, CRITICAL)
   - Кумулятивный риск = Σ(вес_события × возрастающий_коэффициент)
   - Пороги: >70 = Желтая зона, >85 = Красная зона
5. Таблица health_scores:
   - object_id, score, zone (GREEN, YELLOW, RED), calculated_at, contributing_events
6. 5 мелких событий ("сломался бур", "прораб заболел", "дожди") → один большой сигнал
7. Mia: "Денис, на Судакова шторм, критическая масса мелких сбоев"
```

#### 19. Временная ценность документов (Важное замечание пользователя)
```
1. ЗАМЕЧАНИЕ ПОЛЬЗОВАТЕЛЯ: Документ всегда документ, пока его срок действия не закончился,
   либо пока он не изменён/отменён другим документом
2. ОТВЕРГНУТО: Метрика Затухания Контекста (вес чанка падает в зависимости от возраста)
3. ПРИНЯТО: Документы имеют абсолютную ценность до момента официального изменения/отмены
4. Версионирование документов:
   - Документ + все Допы к нему = полный пакет
   - is_current = 1 только для актуальной версии
   - Старые версии сохраняются для истории, но не влияют на текущее состояние
5. Чаты ≠ документы:
   - Чаты имеют динамическую ценность (может потребоваться фильтрация по возрасту)
   - Документы имеют статическую ценность (до официального изменения)
```

#### 20. Модуль интерактивного обучения: Живая Онтология Девиаций
```
1. Human-in-the-loop Grounding (Заземление через человека)
2. Переход от жестких алгоритмических цепочек IF-THEN к Динамическим Пространствам Контекста (Contextual Ontologies)
3. Механизм контекстного сита (Semantic Overlay):
   - Обучение на формировании «гравитационных полей» вокруг базовых строительных концептов
   - Базовые концепты: [Ростелеком], [Все проекты КК], [МГГТ]
   - При разметке экспертом страницы проекта → векторный кластер девиаций в ChromaDB
   - Принудительный контекстный тег (scope) для каждого кластера
4. Few-Shot RAG на 21-м проекте:
   - Модель не ищет совпадение строк
   - Накладывает семантическую маску прошлых уроков на новую спецификацию
   - Выявление смысловых нарушений технологических требований
   - Пример: отсутствие маркировки кабеля HF для Ростелекома или дефицит манжет на объем труб
5. Кристаллизация Онтологии (Ontology Distillation):
   - Devin AI Assistant запускает qwen2.5:14b в фоновом режиме (раз в неделю или по триггеру)
   - Кластеризация накопленных экспертных уроков
   - Обобщение разрозненных комментариев в абстрактные эвристические чек-листы
   - Динамическое обновление системных промптов для «линз внимания» Mia
6. ExpertLessonSchema:
   - lesson_id, doc_category (TECHNICAL_PROJECT, SPECIFICATION, ESTIMATE)
   - context_tags: Смысловые якоря (Ростелеком, Канализация КК, МГГТ)
   - raw_page_text, anchor_text_embedding_id для RAG
   - expert_commentary: Суть урока и комментарий инженера
   - applicability_scope: Граница применимости девиации (выводится Девином)
   - Пример: {"customer": "Ростелеком", "work_type": "канализация", "component": "кабель"}
7. Таблица expert_lessons в SQLite:
   - Хранение экспертных уроков
   - Связь с документами через doc_id
   - Индексация по context_tags для быстрого поиска
   - Флаг verified_by_human для отслеживания качества
```

### RAG интеграция

#### Поиск внутри объекта (гибридный подход)
```
1. Единственная коллекция для всех документов (вместо 108+ коллекций)
2. Строгие метаданные для каждого чанка:
   - object_id: ID папки Google Drive или GLOBAL_REFERENCE
   - doc_id: Уникальный хэш файла
   - doc_category: CONTRACT, ADDENDUM, PROPOSAL, etc.
   - is_current: 1 (актуален) или 0 (архивный)
   - doc_date_timestamp: POSIX timestamp для фильтрации по диапазонам дат
   - chunk_index: Порядковый номер чанка в документе
   - legal_entities: JSON-строка (список ИНН контрагентов)
3. Жесткая фильтрация по метаданным при поиске:
   Filter: object_id == X AND is_current == 1
4. Приоритизация по типу с Reciprocal Rank Fusion (RRF):
   - CONTRACT / ADDENDUM: Вес 1.0
   - FINANCIAL: Вес 0.8
   - PROPOSAL (КП): Вес 0.5
   - REFERENCE (СНИПы): Вес 0.3
5. Версионирование: текущий документ > предыдущие
```

#### Поиск между объектами (двухуровневый подход)
```
Низкоуровневый (Векторный RAG + Метаданные):
1. LLM-агент переводит запрос в структурированный фильтр
   Пример: "все объекты с канализацией для Ростелеком"
   → Filter: customer == "Ростелеком" + векторный поиск по "канализация"

Высокоуровневый (Knowledge Graph / Граф Значений):
1. Легковесный граф поверх SQLite (таблицы entities и object_edges)
2. Таблица entities: entity_id, entity_type (company, object, person)
3. Таблица object_edges: source_id, target_id, edge_type, object_id
4. Типы связей: GEN_CONTRACTOR, SUBCONTRACTOR, CUSTOMER, RELATED_PROJECT
5. При запросе на параллели агент сначала запрашивает граф
   Пример: "кто еще работал с ВэллДан?"
6. Затем вытаскивает документы по найденным ID объектов
```

#### Финансовые запросы: SQL-based подход
```
Запрос: "Сколько вложили в Судакова по НСС1?"

Пайплайн Mia:
1. LLM определяет интент запроса → GET_FINANCIAL_SUMMARY
2. LLM извлекает сущности → object: "Судакова", tom: "НСС1"
3. Mia не считает сама. Генерирует детерминированный SQL-запрос к SQLite
4. Получает точную цифру из БД (например, 4 250 300 руб.)
5. Берет цифру + контекст из ChromaDB → формирует человеческий ответ

Пример ответа:
"По данным учета в объект Судакова (НСС1) вложено 4 250 300 руб.
Однако учтите, что материалы для тома НСС6 закупаются с удорожанием на 20%,
а колодец ККСр-3 был фактически перемещен на Профсоюзную"
```

## API и интерфейсы

### Основные методы
```python
class ObjectDiaryManager:
    def create_diary(self, object_name: str, object_id: str) -> ObjectDiarySchema
    def get_diary(self, object_id: str) -> Optional[ObjectDiarySchema]
    def add_document(self, object_id: str, document: DocumentSchema) -> DiaryEventSchema
    def link_document(self, document: DocumentSchema) -> str  # Returns object_id
    def convert_proposal_to_contract(self, proposal_id: str, contract_id: str)
    def search_within_object(self, object_id: str, query: str) -> List[DocumentSchema]
    def search_between_objects(self, query: str) -> Dict[str, List[DocumentSchema]]
    def get_timeline(self, object_id: str) -> List[DiaryEventSchema]
    def daily_monitoring_pipeline(self)  # Для APScheduler
    def process_pending_link(self, link_task_id: str, object_id: str)  # Inbox обработка
    def run_accuracy_audit(self, object_id: str)  # Контур точности
    def get_financial_summary(self, object_id: str, entity_type: str) -> Dict  # SQL-based
    def process_temporal_context(self, text: str) -> TemporalContextSchema  # Временная логика
```

### Accuracy Contour Manager
```python
class AccuracyContourManager:
    def run_dependency_graph_audit(self, object_id: str) -> AuditResult
    def run_rag_specification_audit(self, object_id: str) -> AuditResult
    def run_temporal_shift_analysis(self, object_id: str) -> AuditResult
    def consensus_arbitration(self, audit_results: List[AuditResult]) -> ConsensusResult
```

### Role Router Manager
```python
class RoleRouterManager:
    def route_question_to_role(self, question: str, object_id: str) -> str  # role_id
    def get_role_users(self, role: str, object_id: str) -> List[str]  # user_ids
    def send_role_notification(self, role: str, object_id: str, message: str)
```

### Virtual Documents Manager
```python
class VirtualDocumentsManager:
    def create_missing_document(self, object_id: str, doc_type: str, deadline: datetime)
    def check_missing_documents(self, object_id: str) -> List[VirtualDocumentSchema]
    def get_lifecycle_checklist(self, object_type: str) -> List[str]
```

### Telegram Distiller
```python
class TelegramDistiller:
    def filter_construction_messages(self, messages: List[str]) -> List[str]
    def distill_events_via_llm(self, messages: List[str]) -> List[ChatLogEvent]
    def add_chat_log_to_diary(self, object_id: str, event: ChatLogEvent)
```

### Temporal Logic Manager
```python
class TemporalLogicManager:
    def inject_absolute_time_context(self, prompt: str) -> str
    def parse_relative_time(self, text: str) -> TemporalContext
    def create_cron_task(self, task: str, relative_time: str) -> datetime
    def execute_cron_tasks(self)  # Запуск планировщика
```

### Alert Dispatcher
```python
class AlertDispatcher:
    def schedule_daily_reminders(self)  # 10:00 - регулярные напоминания
    def schedule_critical_alerts(self)  # 16:00 - критические тревоги
    def send_reminder_summary(self, user_id: str)
    def send_critical_alerts(self, user_id: str, issues: List[str])
```

### Delegation Engine
```python
class DelegationEngine:
    def parse_delegation_request(self, text: str, context: str) -> DelegationRequest
    def find_user_by_name(self, name: str, object_id: str) -> List[UserSchema]
    def resolve_ambiguous_user(self, candidates: List[UserSchema], context: str) -> UserSchema
    def delegate_question(self, request: DelegationRequest, user: UserSchema)
    def intercept_answer(self, message: str, delegated_question_id: str) -> bool
```

### Constraint Manager (Lean Construction)
```python
class ConstraintManager:
    def create_constraint(self, object_id: str, constraint_type: str, description: str) -> ConstraintSchema
    def check_constraints_for_action(self, object_id: str, action: str) -> ConstraintCheckResult
    def satisfy_constraint(self, constraint_id: str, document_id: str) -> bool
    def get_blocking_constraints(self, object_id: str) -> List[ConstraintSchema]
    def evaluate_constraint_network(self, object_id: str) -> NetworkStatus
```

### Intent Classifier
```python
class IntentClassifier:
    def classify_message(self, message: str, context: str) -> IntentSchema
    def validate_intent_against_database(self, intent: IntentSchema) -> ValidationResult
    def fuzzy_match_location(self, location_raw: str) -> Optional[str]  # Returns object_id
    def check_technology_compatibility(self, object_id: str, material_concept: str) -> bool
    def generate_soft_alert(self, intent: IntentSchema, validation_result: ValidationResult) -> str
```

### Negative Event Trigger
```python
class NegativeEventTrigger:
    def create_negative_trigger(self, object_id: str, expected_event: str, deadline: datetime)
    def check_negative_triggers(self) -> List[AlertSchema]
    def evaluate_missing_events(self, object_id: str, deadline: datetime) -> List[str]
    def generate_negative_alert(self, trigger_id: str) -> AlertSchema
```

### Health Score Engine
```python
class HealthScoreEngine:
    def calculate_health_score(self, object_id: str) -> HealthScoreSchema
    def accumulate_risk_factors(self, object_id: str, new_event: DiaryEventSchema)
    def evaluate_cumulative_risk(self, object_id: str) -> CumulativeRiskResult
    def get_risk_zone(self, score: float) -> str  # GREEN, YELLOW, RED
    def generate_health_report(self, object_id: str) -> HealthReport
```

### Expert Teacher (Живая Онтология Девиаций)
```python
class ExpertTeacher:
    def create_lesson(self, doc_category: str, context_tags: List[str], 
                     raw_page_text: str, expert_commentary: str) -> ExpertLessonSchema
    def store_lesson_in_chroma(self, lesson: ExpertLessonSchema) -> str  # Returns embedding_id
    def apply_semantic_overlay(self, new_doc: str, context_tags: List[str]) -> List[ViolationResult]
    def few_shot_rag_analysis(self, project_id: str, spec_text: str) -> FewShotAnalysisResult
    def cluster_lessons(self) -> ClusterResult
    def generate_heuristic_checklists(self) -> List[HeuristicChecklist]
    def update_attention_lenses_prompts(self, checklists: List[HeuristicChecklist])
    def get_relevant_lessons(self, context_tags: List[str]) -> List[ExpertLessonSchema]
```

### DocumentLinker Pipeline
```python
class DocumentLinker:
    async def process_document_pipeline(self, document: DocumentSchema) -> LinkResult:
        # Паттерн "Трубопровод" (Pipeline Interceptor)
        # 1. Regex/Эвристики (ИНН, адреса, коды объектов)
        # 2. LLM Ollama Classifier (если эвристики не дали Confidence > 0.90)
        # 3. Выход: Ассоциация с ID объекта или отправка в pending_links
        pass
```

### Inbox Manager
```python
class InboxManager:
    def create_pending_link(self, document: DocumentSchema, suggested_objects: List[Dict])
    def resolve_pending_link(self, link_task_id: str, object_id: str)
    def get_pending_links(self, status: str = None) -> List[PendingLinkSchema]
```

### Внешние интерфейсы
- GUI для просмотра дневников объектов
- Telegram команды для запроса информации по объектам
- Автоматические уведомления о новых документах
- Inbox-интерфейс для ручного разрешения неоднозначных связей

## Метрики качества разработки (по RFC-032)

Три численные метрики оценки самой Mia для контроля качества и надежности:

### 1. Autonomy Rate
- **Определение**: Процент автоматически разобранных документов без ручной правки
- **Целевой показатель**: > 80%
- **Расчет**: `(автоматически_связанные_документы / общее_количество_документов) * 100`
- **Мониторинг**: Ежедневный расчет, трекинг во времени
- **Алерт при падении**: Если Autonomy Rate падает ниже 70% → алерт на снижение качества

### 2. Число ложных SUCCESS
- **Определение**: Количество сбоев, когда система заявила об успехе (например, извлечении денег), но детерминированный SQL-тест не сошелся
- **Целевой показатель**: < 5 ложных SUCCESS за неделю
- **Расчет**: Подсчет случаев где `success == True` но `sql_validation == False`
- **Мониторинг**: Еженедельный отчет, анализ причин
- **Алерт при превышении**: Если > 10 ложных SUCCESS за неделю → анализ архитектором

### 3. LLM Call Budget
- **Определение**: Ограничение бюджета токенов/времени на один запрос для защиты RTX 5060 от зацикливания модели
- **Лимиты**:
  - Максимальное время на один запрос: 30 секунд
  - Максимальное количество токенов на один запрос: 4000 токенов
  - Максимальное количество параллельных запросов: 2 (асинхронный семафор)
- **Мониторинг**: Отслеживание времени инференса, количества токенов
- **Алерт при превышении**: Если запрос превышает лимит → прерывание и логирование
- **Защита RTX 5060**: Мониторинг VRAM, автоматическое ограничение при 80% загрузке

### Таблица метрик качества (SQLite)
```sql
CREATE TABLE quality_metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,  -- autonomy_rate, false_success_count, llm_call_budget
    metric_value REAL NOT NULL,
    measurement_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    threshold_limit REAL,
    is_critical BOOLEAN DEFAULT FALSE
);
```

### Telegram Integration
```python
# Интеграция с python-telegram-bot или aiogram
class InboxRouter:
    def send_pending_link_notification(self, task_id: str, document: DocumentSchema)
    # Инлайн-кнопки: callback_data="link_doc:{task_id}:{object_id}"
```

### APScheduler Integration
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
scheduler.add_job(
    func=ObjectDiaryManager.daily_monitoring_pipeline,
    trigger='cron',
    hour=2,
    minute=0
)
scheduler.start()
```

### ChromaDB Integration
```python
import chromadb

chroma_client = chromadb.PersistentClient(path="./chroma_db")
rag_collection = chroma_client.get_or_create_collection(name="object_diary_chunks")

# Поиск с жесткой фильтрацией
results = rag_collection.query(
    query_texts=[query],
    where={"object_id": object_id, "is_current": 1}
)
```

### Ollama Integration
```python
import ollama

# Рекомендуемые модели: deepseek-coder:6.7b или llama3.1:8b
# Обязательный параметр format="json" для валидации Pydantic схем
response = ollama.chat(
    model="deepseek-coder:6.7b",
    messages=[...],
    format="json"
)
```

## Вопросы для обсуждения

### Технические вопросы
1. **Как хранить документы в RAG?** ✅ РЕШЕНО: Гибридный подход с единой коллекцией и жестким мета-фильтрованием (object_id, doc_id, doc_category, is_current, doc_date_timestamp, chunk_index, legal_entities)
2. **Как реализовать поиск между объектами?** ✅ РЕШЕНО: Двухуровневый подход: низкоуровневый (RAG + метаданные) + высокоуровневый (Knowledge Graph поверх SQLite)
3. **Как обрабатывать ошибки связывания?** ✅ РЕШЕНО: Human-in-the-loop через Inbox с динамическим confidence threshold (0.90, 0.70)

### Архитектурные вопросы
1. **Нужен ли отдельный модуль для связывания документов?** ✅ РЕШЕНО: Да, обязательно выделить в отдельный сервис DocumentLinker. DiaryManager отвечает только за CRUD и консистентность данных. DocumentLinker - изолированный пайплайн (эвристики + LLM) для легкой замены модели классификации или добавления OCR.
2. **Как организовать справочную ветку?** ✅ РЕШЕНО: Категория в основной таблице документов с object_id = "GLOBAL_REFERENCE". Не выделять в отдельную таблицу - та же текстовая структура для RAG. Специальный системный ID для подмешивания в поиск.
3. **Как работать с уже существующими 108 объектами?** ✅ РЕШЕНО: Пакетная миграция в 3 этапа:
   - Детерминированный скрипт: базовая структура из названий папок Google Drive
   - Асинхронный LLM-пайплайн: фоновая классификация 6295 файлов
   - Сессия валидации: отчет "Связано уверенно: 85%, требует проверки: 15%"

### UX вопросы
1. **Как просить пользователя о неоднозначных случаях?** ✅ РЕШЕНО: Human-in-the-loop через "Inbox" (Входящие). Интерактивная карточка в GUI/Telegram с выбором объекта или созданием нового.
2. **Как отображать временные шкалы?** (визуализация, фильтры, экспорт?)
3. **Как работать с версиями документов?** ✅ РЕШЕНО: Отображать весь пакет (Договор + все Допы к нему). Визуализация diff между версиями. Подсветка места в документе при клике на сумму (через цитирование).

### Новые архитектурные решения от Google AI v4

#### Контур точности: Тройной перекрестный аудит дедлайнов и показателей
1. **Метод 1: Детерминированный Граф Зависимостей (NetworkX)** ✅ РЕШЕНО: Жесткий код на Python-библиотеке NetworkX, неизменные правила строительного ГОСТа, чистая математика без LLM
2. **Метод 2: Критический RAG по Спецификациям (Ollama 8B)** ✅ РЕШЕНО: mistral:7b-instruct-v0.3 сравнивает сущности, находит аномалии во времени и деньгах
3. **Метод 3: Анализатор Временных Сдвигов (Ollama 14B)** ✅ РЕШЕНО: qwen2.5:14b-instruct-q4_K_M читает Telegram-переписку, ловит неформальные дедлайны
4. **Консенсус-Арбитр** ✅ РЕШЕНО: Специальный промпт собирает выводы трех методов, бьет в набат при критических нарушениях

#### Адресный Human-in-the-loop: Умная маршрутизация вопросов
1. **Матрица компетенций ролей (system_roles)** ✅ РЕШЕНО: Таблица SQLite с user_id, role (LEGAL, PROCTOR, PURCHASING, PROJECT_ENG), object_id
2. **Логика маршрутизации** ✅ РЕШЕНО: Юридические вопросы → Юрист/ГИП, логистика → Прораб/Снабженец
3. **Интерактивные карточки** ✅ РЕШЕНО: Пуш в Telegram с inline-кнопками Да/Нет для подтверждения

#### Учет фантомных (отсутствующих) документов - Shadow Document pattern
1. **Жизненный цикл Объекта** ✅ РЕШЕНО: Детерминированный чек-лист обязательных документов для каждого типа объекта
2. **Shadow Document pattern** ✅ РЕШЕНО: Таблица virtual_documents со статусом MISSING, дедлайн (Дата_Договора + 14 дней)
3. **Поиск RAG** ✅ РЕШЕНО: ChromaDB → реальные чанки, SQLite → список MISSING документов

#### Агрегация хаоса: Слияние документов и Telegram-каналов
1. **Event Distiller pattern** ✅ РЕШЕНО: Regex-фильтрация ключевых слов (кабель, колодец, привезли, ОАТИ, штамп, подписали)
2. **LLM обработка** ✅ РЕШЕНО: mistral:7b раз в час или по триггеру, промпт "Выдели строительные факты"
3. **CHT_LOG события** ✅ РЕШЕНО: Дистиллированные факты пишутся в diary_events, в ChromaDB уходят только факты
4. **Скриптинг анализа разговоров** ❌ ОТВЕРГНУТО ПОЛЬЗОВАТЕЛЕМ: Пропускаем через логику LLM для summary написанного

#### Финансовые запросы: SQL-based подход
1. **GET_FINANCIAL_SUMMARY intent** ✅ РЕШЕНО: LLM определяет интент, извлекает сущности (object, tom)
2. **Детерминированный SQL** ✅ РЕШЕНО: Mia генерирует SQL-запрос к SQLite, получает точную цифру из БД
3. **Контекст из ChromaDB** ✅ РЕШЕНО: Берет цифру + контекст (строка из чата), формирует человеческий ответ

#### Модели Ollama под RTX 5060 16Gb
1. **Классификация и извлечение сущностей** ✅ РЕШЕНО: mistral:7b-instruct-v0.3 или llama3.1:8b-instruct-q8_0 (Q8 для минимизации ошибок в цифрах)
2. **Анализ связей и логических цепочек** ✅ РЕШЕНО: qwen2.5:14b-instruct-q4_K_M (9-10 ГБ VRAM, качество выше 8B)
3. **Эмбеддинги** ✅ РЕШЕНО: nomic-embed-text (<1 ГБ, постоянно в памяти параллельно с основной LLM)

#### Rate limiting и обработка ошибок Ollama
1. **Монопольный доступ** ✅ РЕШЕНО: asyncio.Semaphore(1) для генерации, параллельный CPU-bound парсинг текста
2. **Tenacity retry policy** ✅ РЕШЕНО: Экспоненциальный бэккофф на ConnectError и TimeoutError, максимум 3 повтора
3. **PARSING_FAILED статус** ✅ РЕШЕНО: Маркировка документа как PARSING_FAILED при повторных ошибках

#### Кэширование LLM-анализа документов
1. **SHA-256 хэш файла** ✅ РЕШЕНО: Кэширование по хэшу файла в SQLite таблице parsed_files_cache
2. **Проверка версии промпта/модели** ✅ РЕШЕНО: Если версия изменилась → повторный анализ
3. **Экономия GPU** ✅ РЕШЕНО: Мгновенная отдача старого JSON при перезапусках миграции

#### UX решения для сложных временных шкал
1. **Side-by-Side Diff** ✅ РЕШЕНО: Двухпанельный интерфейс, подсветка измененных сущностей в карточке Дневника
2. **Threaded Timelines** ✅ РЕШЕНО: Сворачиваемые цепочки, договор как корневой узел, доп. соглашения как ветки
3. **PDF-вьювер с подсветкой** ✅ РЕШЕНО: Модальное окно, scrollToPage + highlight по citation_page и citation_text
4. **Локальный Knowledge Graph** ✅ РЕШЕНО: vis.js или Cytoscape.js, график вокруг выбранного объекта

#### Продуктовые решения
1. **Агрегированные уведомления** ✅ РЕШЕНО: Пуш в Telegram раз в час, статистика по батчу
2. **Приоритизация Inbox** ✅ РЕШЕНО: Confidence Score (снизу вверх) + Тип документа (CONTRACT/ADDENDUM первыми)
3. **Autonomy Rate метрика** ✅ РЕШЕНО: Процент автоматических связываний, которые человек не перепривязал (>80% цель)
4. **Shadow Deploy A/B тестирование** ✅ РЕШЕНО: Теневой пайплайн с ab_test_logs таблицей

#### Интеграционные решения
1. **SQLite совместимость** ✅ РЕШЕНО: Новые таблицы с foreign key на basic_project_ledgers(id)
2. **Бэкап и восстановление** ✅ РЕШЕНО: Cron-скрипт в 03:00, tar.gz архив, отправка в Google Drive
3. **OAuth авторизация** ✅ РЕШЕНО: Токены Google Drive, доступ к папке = доступ к Дневнику
4. **Мониторинг системы** ✅ РЕШЕНО: Prometheus + Grafana, Loguru, мониторинг VRAM, времени инференса, ошибок

### 🔍 Новые вопросы для обсуждения

#### Технические вопросы
1. **Какой confidence threshold выбрать для связывания документов?** (0.85 предложено, но может быть 0.75 или 0.90?)
2. **Какие метаданные добавить для каждого чанка в RAG?** (нужны ли дополнительные поля помимо object_id, document_category, is_current, date?)
3. **Как организовать асинхронный LLM-пайплайн для миграции?** (queue, rate limiting, batch processing?)
4. **Как реализовать Knowledge Graph поверх SQLite?** (какая структура таблицы object_edges, какие типы связей?)

#### Архитектурные вопросы
1. **Как организовать Inbox для pending_links?** (отдельная таблица, очередь сообщений, интеграция с GUI?)
2. **Как интегрировать DocumentLinker с существующей системой парсинга?** (общий пайплайн или отдельные потоки?)
3. **Как хранить цитаты для защиты от галлюцинаций?** (в DiaryEventSchema или отдельная таблица citations?)
4. **Как организовать diff-визуализацию между версиями документов?** (какие библиотеки, какие метрики?)

#### UX вопросы
1. **Как отображать временные шкалы в GUI?** (timeline view, gantt chart, custom visualization?)
2. **Какие фильтры нужны для временных шкал?** (по типу события, по дате, по контрагенту?)
3. **Как организовать экспорт временных шкал?** (Excel, PDF, JSON?)
4. **Как подсвечивать цитаты в документах при клике на сумму?** (PDF viewer, разметка, интеграция с парсером?)

#### Продуктовые вопросы
1. **Какие отчеты нужны для валидации миграции?** (процент уверенности, список ошибок, категории проблем?)
2. **Как часто обновлять confidence scores для существующих связей?** (пересчет при новых данных, периодический пересчет?)
3. **Как обрабатывать конфликтующие цитаты?** (если разные документы дают разные суммы для одного поля?)
4. **Как приоритизировать типы документов в RAG?** (веса для CONTRACT vs PROPOSAL vs REFERENCE?)

#### Интеграционные вопросы
1. **Как интегрировать DiaryManager с существующими Telegram handlers?** (новые команды, расширение существующих?)
2. **Как интегрировать с APScheduler для ежедневного мониторинга?** (задачи cron, rate limiting)
3. **Как интегрировать с ChromaDB для RAG?** (коллекции, метаданные, фильтрация)
4. **Как интегрировать с Ollama для LLM-анализа документов?** ✅ РЕШЕНО: deepseek-coder:6.7b или llama3.1:8b с format="json"

### ✅ Все вопросы решены (Google AI v6)

#### Контур точности и независимые контуры
1. **Контур точности: Тройной перекрестный аудит** ✅ РЕШЕНО: NetworkX (детерминированный) + RAG (mistral:7b) + Анализ временных сдвигов (qwen2.5:14b)
2. **Адресный Human-in-the-loop** ✅ РЕШЕНО: Матрица компетенций ролей (system_roles), умная маршрутизация вопросов
3. **Shadow Document pattern** ✅ РЕШЕНО: Жизненный цикл объекта, таблица virtual_documents, статус MISSING
4. **Event Distiller pattern** ✅ РЕШЕНО: Regex-фильтрация + LLM summary, без скриптинга анализа разговоров
5. **SQL-based финансовые запросы** ✅ РЕШЕШО: Детерминированные SQL вместо LLM-суммирования

#### Темпоральная логика и динамическая делегация (Google AI v5)
1. **Absolute Time Injection** ✅ РЕШЕНО: Инъекция абсолютного времени в промпт, относительные переводы (Сегодня/Завтра/Вчера)
2. **Detермinistic time parsing** ✅ РЕШЕНО: LLM парсит фразу → JSON, бэкенд математически вычисляет абсолютную дату
3. **Cron tasks в SQLite** ✅ РЕШЕНО: Таблица cron_tasks с фиксированными датами выполнения
4. **Диспетчер Алертов** ✅ РЕШЕНО: APScheduler, регулярные напоминания (10:00), критические тревоги (16:00)
5. **Паттерн «Спроси у Светы»** ✅ РЕШЕНО: Граф ролей в SQLite, контекстный парсинг имен, выбор канала связи
6. **Перехват ответа** ✅ РЕШЕНО: Таблица delegated_questions со статусом AWAITING_REPLY, mistral:7b парсит ответы
7. **Многозначность имен** ✅ РЕШЕНО: Human-in-the-loop при нескольких совпадениях, инлайн-кнопки выбора
8. **Изменение дедлайнов «задним числом»** ✅ РЕШЕНО: Статус PROLONGED_BY_CHAT, снижение критичности алерта до желтого

#### Технические решения под RTX 5060 16Gb
1. **Модели Ollama** ✅ РЕШЕНО: mistral:7b Q8 (классификация), qwen2.5:14b Q4 (анализ связей), nomic-embed-text (эмбеддинги)
2. **Rate limiting** ✅ РЕШЕНО: asyncio.Semaphore(1) для монопольного доступа, параллельный CPU-bound парсинг
3. **Ошибки сети Ollama** ✅ РЕШЕНО: tenacity с экспоненциальным бэккоффом, PARSING_FAILED статус
4. **Кэширование LLM-анализа** ✅ РЕШЕНО: SHA-256 хэш файла в SQLite, проверка версии промпта/модели

#### UX решения
1. **Diff-визуализация** ✅ РЕШЕНО: Side-by-Side Diff, подсветка измененных сущностей в карточке
2. **Сложные временные шкалы** ✅ РЕШЕНО: Threaded Timelines (сворачиваемые цепочки), договор как корневой узел
3. **Поиск по цитатам** ✅ РЕШЕНО: Модальное окно с PDF-вьювером, scrollToPage + highlight
4. **Knowledge Graph** ✅ РЕШЕНО: vis.js или Cytoscape.js, локальный граф вокруг объекта

#### Продуктовые решения
1. **Уведомления pending_links** ✅ РЕШЕНО: Агрегированные пуш в Telegram раз в час
2. **Приоритизация Inbox** ✅ РЕШЕНО: Confidence Score + Тип документа (CONTRACT/ADDENDUM первыми)
3. **Качество связывания** ✅ РЕШЕНО: Autonomy Rate (>80% цель)
4. **A/B тестирование** ✅ РЕШЕНО: Shadow Deploy с ab_test_logs таблицей

#### Интеграционные решения
1. **SQLite совместимость** ✅ РЕШЕНО: Новые таблицы с foreign key на basic_project_ledgers(id)
2. **Бэкап и восстановление** ✅ РЕШЕНО: Cron-скрипт в 03:00, tar.gz архив, Google Drive
3. **OAuth авторизация** ✅ РЕШЕНО: Токены Google Drive, доступ к папке = доступ к Дневнику
4. **Мониторинг системы** ✅ РЕШЕНО: Prometheus + Grafana, Loguru, VRAM, время инференса, ошибки

#### Lean Construction и стохастическое управление (Google AI v6)
1. **Lean Construction + Last Planner System** ✅ РЕШЕНО: Сеть Условий и Ограничений вместо жесткой цепи
2. **Constraint Management** ✅ РЕШЕНО: Объект = бассейн событий + сито ограничений, проверка блокирующих условий
3. **Intent Classifier** ✅ РЕШЕНО: Анализатор Намерений на Базовых Концептах вместо жестких скриптов
4. **Детерминированная валидация** ✅ РЕШЕНО: Python-код страхует LLM от ошибок, нечеткий поиск по базе объектов
5. **Negative Event Trigger** ✅ РЕШЕНО: Триггеры на «Молчание» (отсутствие события = алерт)
6. **Кумулятивный риск (Health Score)** ✅ РЕШЕНО: Индекс Здоровья Объекта, кумуляция мелких событий → красная зона
7. **Временная ценность документов** ✅ РЕШЕНО: Документы имеют абсолютную ценность до официального изменения/отмены
8. **Context Decay Metric** ❌ ОТВЕРГНУТО ПОЛЬЗОВАТЕЛЕМ: Документ всегда документ, пока срок действия не закончился

#### Интерактивное обучение (Google AI v8)
1. **Human-in-the-loop Grounding** ✅ РЕШЕНО: Заземление через человека без Fine-Tuning весов модели
2. **Динамические Пространства Контекста** ✅ РЕШЕНО: Contextual Ontologies вместо жестких IF-THEN цепочек
3. **Механизм контекстного сита (Semantic Overlay)** ✅ РЕШЕНО: Гравитационные поля вокруг базовых концепций
4. **Few-Shot RAG** ✅ РЕШЕНО: Семантическая маска прошлых уроков на новые спецификации
5. **Кристаллизация Онтологии** ✅ РЕШЕНО: Devin AI Assistant обобщает уроки в эвристические чек-листы
6. **ExpertLessonSchema** ✅ РЕШЕНО: context_tags, raw_page_text, expert_commentary, applicability_scope
7. **ExpertTeacher модуль** ✅ РЕШЕНО: Создание уроков, семантический поиск, кластеризация

## Порядок Jobs для слабых LLM (кодогенерация)

Для реализации RFC v1.7 слабые LLM (Gemma 3 12B / Qwen 3 Coder 14B) будут генерировать код в следующем порядке:

### Фаза 1: Базовая инфраструктура (Job #1-#5)
1. **Job #1: Схемы Pydantic**
   - Реализовать ObjectDiarySchema, DiaryEventSchema, TemporalContextSchema
   - Реализовать IntentSchema, ConstraintSchema, HealthScoreSchema
   - Реализовать DelegationRequestSchema, DelegatedQuestionSchema
   - Добавить ConfigDict для всех схем
   - Проверить валидацию данных

2. **Job #2: SQLite Database Schema**
   - Создать таблицы: objects, diary_events, virtual_documents
   - Создать таблицы: constraints, constraint_dependencies, constraint_status
   - Создать таблицы: system_roles, delegated_questions, negative_events_triggers
   - Создать таблицы: health_scores, cron_tasks, parsed_files_cache
   - Настроить foreign keys и индексы

3. **Job #3: Базовый DiaryManager**
   - CRUD операции: create_diary, get_diary, update_diary
   - Работа с событиями: add_event, get_timeline, delete_event
   - Версионирование: overrides_event_id, is_current
   - Цитирование: citation_text, citation_page, citation_confidence

4. **Job #4: ChromaDB интеграция**
   - Инициализация PersistentClient
   - Создание единой коллекции object_diary_chunks
   - Метаданные чанков: object_id, doc_id, doc_category, is_current, chunk_index
   - Жесткая фильтрация по where
   - Reciprocal Rank Fusion (RRF) с весами

5. **Job #5: Ollama клиент и базовые промпты**
   - Инициализация ollama клиента
   - Модели: mistral:7b, qwen2.5:14b, nomic-embed-text
   - Базовые промпты для классификации и извлечения
   - Формат JSON для валидации Pydantic схем
   - SHA-256 кэширование результатов

### Фаза 2: Контур точности (Job #6-#8)
6. **Job #6: AccuracyContourManager - Метод 1 (NetworkX)**
   - Реализовать детерминированный граф зависимостей
   - Правила строительного ГОСТа и регламентов
   - Проверка ограничений: check_constraints_for_action
   - Поддержка BYPASS_STRICT_RULE флага
   - Возврат статуса: BLOCK, WARNING, OK

7. **Job #7: AccuracyContourManager - Метод 2 (RAG)**
   - Изолированное сравнение сущностей
   - Поиск аномалий во времени и деньгах
   - Интеграция с ChromaDB для спецификаций
   - Промпты для mistral:7b
   - Возврат списка аномалий

8. **Job #8: AccuracyContourManager - Метод 3 (Telegram)**
   - Анализатор временных сдвигов
   - Чтение Telegram-переписки
   - Сопоставление с официальными документами
   - Поддержка BYPASS_STRICT_RULE для Метода 1
   - Промпты для qwen2.5:14b

9. **Job #9: AccuracyContourManager - Консенсус-Арбитр**
   - Сбор выводов трех методов
   - Разрешение конфликтов между методами
   - Генерация финального решения
   - Логика "Пакта о помиловании"
   - Промпт для консенсуса

### Фаза 3: Управление ограничениями (Job #10-#12)
10. **Job #10: ConstraintManager**
    - CRUD для ограничений
    - Сеть Условий и Ограничений
    - severity_level: CRITICAL, MAJOR, MINOR
    - Проверка блокирующих условий
    - Жесткая блокировка для CRITICAL ограничений

11. **Job #11: IntentClassifier**
    - Классификация сообщений на базовых концептах
    - Промпт для mistral:7b (JSON режим)
    - Детерминированная валидация
    - Нечеткий поиск по базе объектов
    - Проверка технологической совместимости

12. **Job #12: NegativeEventTrigger**
    - Создание триггеров на «Молчание»
    - Проверка отсутствия событий
    - Ежедневная проверка через APScheduler
    - Генерация алертов на основе отсутствия
    - Таблица negative_events_triggers

### Фаза 4: Кумулятивный риск (Job #13-#14)
13. **Job #13: HealthScoreEngine**
    - Расчет Индекса Здоровья Объекта
    - Кумуляция мелких событий
    - Пороги: GREEN, YELLOW, RED
    - Учет severity_level ограничений
    - Генерация отчета о рисках

14. **Job #14: Integration ConstraintManager + HealthScore**
    - Интеграция ограничений в Health Score
    - Жесткая блокировка для CRITICAL
    - Кумулятивный риск от нескольких ограничений
    - Генерация алертов по зонам
    - Визуализация риска

### Фаза 5: Темпоральная логика (Job #15-#17)
15. **Job #15: TemporalLogicManager**
    - Absolute Time Injection в промпты
    - Relative Translation Map (Сегодня/Завтра/Вчера)
    - Детерминистический time parsing
    - Создание cron_tasks в SQLite
    - Исполнение cron задач

16. **Job #16: AlertDispatcher**
    - APScheduler для регулярных напоминаний (10:00)
    - APScheduler для критических тревог (16:00)
    - Рабочее время: 9:00 - 18:00
    - Агрегация уведомлений
    - Telegram рассылка

17. **Job #17: Integration TemporalLogic + AlertDispatcher**
    - Связывание cron задач с алертами
    - Проверка NegativeEventTrigger
    - Генерация сводок за день
    - Генерация критических отчетов

### Фаза 6: Динамическая делегация (Job #18-#20)
18. **Job #18: DelegationEngine**
    - Парсинг запросов делегирования
    - Поиск пользователей по имени (system_roles)
    - Выбор канала связи (PRIVATE/PUBLIC)
    - Логика эскалации (deadline_for_reply, reminder_count)
    - Transfer to user if no answer in 24h

19. **Job #19: RoleRouterManager**
    - Матрица компетенций ролей
    - Умная маршрутизация вопросов
    - LEGAL → Юрист/ГИП, LOGISTICS → Прораб/Снабженец
    - Интерактивные карточки с инлайн-кнопками
    - Telegram интеграция

20. **Job #20: Integration Delegation + RoleRouter**
    - Полный цикл делегирования
    - Перехват ответов
    - Эскалация зависших вопросов
    - Логирование всех операций
    - Уведомления о статусе

### Фаза 7: Документы и связывание (Job #21-#24)
21. **Job #21: DocumentLinker**
    - Паттерн "Трубопровод" (Pipeline Interceptor)
    - Regex/Эвристики (ИНН, адреса, коды объектов)
    - LLM классификация (если эвристики не дали Confidence > 0.90)
    - Динамический confidence threshold (0.90, 0.70)
    - Выход: ассоциация с ID объекта или pending_links

22. **Job #22: InboxManager**
    - Таблица pending_links
    - Интерактивные карточки в GUI/Telegram
    - Обработка неоднозначных случаев
    - Confidence Score фильтрация
    - Разрешение связей

23. **Job #23: VirtualDocumentsManager**
    - Shadow Document pattern
    - Жизненный цикл объекта
    - Таблица virtual_documents со статусом MISSING
    - Чек-лист обязательных документов
    - Дедлайны для MISSING документов

24. **Job #24: TelegramDistiller**
    - Event Distiller pattern
    - Regex-фильтрация ключевых слов
    - LLM обработка (mistral:7b) для summary
    - Запись CHAT_LOG в diary_events
    - Векторизация только фактов в ChromaDB

### Фаза 8: RAG и поиск (Job #25-#27)
25. **Job #25: Поиск внутри объекта**
    - Жесткая фильтрация по object_id и is_current
    - Reciprocal Rank Fusion (RRF) с весами
    - Приоритизация: CONTRACT 1.0, FINANCIAL 0.8, PROPOSAL 0.5, REFERENCE 0.3
    - Версионирование документов
    - Пакетная отдача (Договор + все Допы)

26. **Job #26: Поиск между объектами**
    - Низкоуровневый: RAG + метаданные
    - Высокоуровневый: Knowledge Graph (SQLite)
    - Таблицы entities и object_edges
    - Типы связей: GEN_CONTRACTOR, SUBCONTRACTOR, CUSTOMER
    - Параллели между объектами

27. **Job #27: SQL-based финансовые запросы**
    - GET_FINANCIAL_SUMMARY intent
    - Детерминированные SQL запросы к SQLite
    - Точные цифры из БД
    - Контекст из ChromaDB
    - Человеческий ответ с контекстом

### Фаза 9: Интеграция и мониторинг (Job #28-#30)
28. **Job #28: Мониторинг папки "Договоры"**
    - APScheduler ежедневный мониторинг (02:00 ночи)
    - Детекция новых документов
    - Классификация документов
    - Запуск DocumentLinker
    - Интеграция в систему дневников

29. **Job #29: Пакетная миграция существующих объектов**
    - Детерминированный скрипт: базовая структура из названий папок
    - Асинхронный LLM-пайплайн: классификация 6295 файлов
    - SHA-256 кэширование для экономии GPU
    - Сессия валидации: отчет с процентами уверенности
    - Миграция 108 существующих объектов

30. **Job #30: Мониторинг и метрики**
    - Prometheus + Grafana интеграция
    - Loguru для логирования
    - Мониторинг VRAM, времени инференса, ошибок
    - Autonomy Rate метрика (>80% цель)
    - Shadow Deploy A/B тестирование

### Фаза 10: Интерактивное обучение (Job #31-#33)
31. **Job #31: ExpertTeacher - Базовая инфраструктура**
    - Таблица expert_lessons в SQLite
    - ExpertLessonSchema с context_tags, raw_page_text, expert_commentary
    - ChromaDB коллекция для экспертных уроков
    - Хранение embedding_id для семантического поиска
    - Интерфейс для создания уроков экспертом

32. **Job #32: ExpertTeacher - Semantic Overlay и Few-Shot RAG**
    - Механизм контекстного сита (Semantic Overlay)
    - Формирование «гравитационных полей» вокруг базовых концепций
    - Few-Shot RAG для наложения семантической маски на новые спецификации
    - Выявление смысловых нарушений технологических требований
    - Поиск релевантных уроков по context_tags

33. **Job #33: ExpertTeacher - Кристаллизация Онтологии**
    - Devin AI Assistant: qwen2.5:14b для кластеризации уроков
    - Обобщение разрозненных комментариев в эвристические чек-листы
    - Динамическое обновление системных промптов для «линз внимания»
    - APScheduler для фонового режима (раз в неделю или по триггеру)
    - Интеграция с IntentClassifier для применения уроков

## План реализации

> Статус: ✅ все этапы реализованы (см. v1.10 и Todo.md 8.7–8.16).

### Этап 1: RFC обсуждение и утверждение
- [x] Обсудить этот RFC с заказчиком
- [x] Уточнить архитектурные решения
- [x] Утвердить план реализации

### Этап 2: Базовая структура дневников
- [x] Реализовать ObjectDiarySchema
- [x] Реализовать DiaryEventSchema
- [x] Создать менеджер дневников
- [x] Настроить хранение в SQLite

### Этап 3: Мониторинг папки "Договоры"
- [x] Реализовать ежедневный мониторинг
- [x] Классификация документов
- [x] Детекция новых документов

### Этап 4: Связывание документов
- [x] Анализ текста для определения объектов
- [x] Алгоритм связывания документов
- [x] Обработка неоднозначных случаев

### Этап 5: КП → Договор
- [x] Отслеживание КП
- [x] Конверсия в объекты
- [x] История переходов

### Этап 6: Иерархия договоров
- [x] Анализ текста для связей
- [x] Создание структуры связей
- [x] Визуализация иерархии

### Этап 7: Справочная ветка
- [x] Классификация справочных документов
- [x] Отдельное хранение
- [x] Интеграция в поиск

### Этап 8: RAG интеграция
- [x] Поиск внутри объекта
- [x] Поиск между объектами
- [x] Версионирование документов

### Этап 9: GUI и Telegram
- [x] Интерфейс для просмотра дневников
- [x] Команды для запросов
- [x] Уведомления

### Этап 10: Тестирование и отладка
- [x] Миграция существующих объектов
- [x] Тестирование на реальных данных
- [x] Отладка связывания

## Риски и митигация

> Статус 2026-10-19: покрыто тестами `tests/test_object_diary.py` (DocumentLinker, RAG state replay, contract parsing).

### Риск 1: Ошибки связывания документов
- **Митигация**: Правило спрашивать пользователя при неоднозначности
- **Митигация**: Логирование всех решений связывания

### Риск 2: Производительность RAG
- **Митигация**: Оптимизация поисковых запросов
- **Митигация**: Кэширование результатов

### Риск 3: Сложность анализа текста
- **Митигация**: Начать с простых правил, постепенно усложнять
- **Митигация**: Использовать LLM для сложных случаев

## Дополнительные материалы

### Связанные RFC
- [RFC Google Drive Analysis](docs/rfc_google_drive_analysis.md)
- [Project Ledger Schema](ai.md)

### Примеры данных
- Пример структуры дневника объекта
- Пример связывания документов
- Пример иерархии договоров

## Безопасность и надежность (по RFC-032)

### Трехконтурная Архитектура Системы
- **Companion (Контур диалога)**: Telegram-клиент, чтение состояний, регистрация запросов. Запрещено прямое изменение БД и генерация кода.
- **Studio (Контур детерминированных рецептов)**: Выполнение жесткого Python/SQL-кода (NetworkX, SQL-запросы к деньгам, базовые парсеры). Логика жестко зафиксирована.
- **Workshop (Контур исследований Devin)**: Изолированная зона, где Devin генерирует новые промпты, кодовые обработчики и "линзы внимания" на основе таблицы уроков expert_lessons.

### Паттерн "CodeCandidate"
- Любой код, SQL-запрос или промпт, сгенерированный слабой моделью (8B) получает статус CodeCandidate
- Сохранение строго в директорию `sandbox/candidates/`
- Прямая запись в живые модули ядра `app/modules/` ЗАПРЕЩЕНА
- Допуск в основную систему только после прохождения Subprocess-Smoke и Hash-Bound Admission

### Изоляция Исполнения (Subprocess-Smoke)
- Запрет in-process импорт (`importlib.import_module`) непроверенных кандидатов кода
- Тестирование кандидата через запуск независимого изолированного `subprocess`
- Допуск (Admission Gate) в контур Studio только при возврате `Exit Code == 0` и маркере `SMOKE_OK`

### Допуск по Хэшу (Hash-Bound Admission)
- Каждое допущенное правило проверки, промпт или SQL-шаблон подписывается SHA-256 хэшем
- Любое несанкционированное изменение файла слабой моделью аннулирует хэш
- Модуль переводится в статус `BLOCKED` до ручной проверки архитектором (Devin)

### Продуктовая система метрик качества
- **Autonomy Rate**: Процент автоматически разобранных документов без ручной правки (>80% цель)
- **Число ложных SUCCESS**: Количество сбоев при заявленном успехе (<5 за неделю цель)
- **LLM Call Budget**: Ограничение бюджета токенов/времени на один запрос для защиты RTX 5060

## Версионирование RFC

### v1.10 (2026-10-19) — Реализация завершена
- Статус RFC переведён в ✅ COMPLETED: Jobs #1–#33 реализованы в `app/modules/object_diary/`
- Все 17 модулей покрыты тестами (`tests/test_object_diary.py`, 119 тестов)
- Схема БД приведена в соответствие с кодом: добавлены таблицы `object_events` и `invoices`
  (`app/modules/storage/database.py` — источник истины)
- Модули переписаны под реальные колонки: `constraint_manager` (`constraint_name`,
  `required_for_actions`, статусы NOT_SATISFIED/SATISFIED/WAIVED), `virtual_documents`,
  `expert_teacher`, `constraint_health_integration`
- `telegram_distiller`: резолв Telegram-чата через `projects`, чтение `message_text`,
  дедупликация рисков и таймлайна
- `contract_analyzer`: корректный парсинг номера (кириллица), даты и сумм с разделителями
- `document_info_extractor` / `contract_analyzer` / `rag.document_ingestor`: переход на
  `DocumentParserFactory` (у `DocumentParser` нет `parse_document`)
- `app/modules/temporal/` восстановлен (модули лежали в `archive/` как `*_duplicate.py`);
  добавлены тесты `tests/test_temporal_module.py` (23 теста)
- Исправлен `gui/mia_gui.py`: `TemporalLogic` → `TemporalLogicManager` (NameError в чате)

### v1.9 (2026-09-20)
- Добавлены паттерны надежности по гигиене проекта (RFC-032)
- Трехконтурная архитектура: Companion, Studio, Workshop
- Паттерн "CodeCandidate" для защиты ядра от генерации слабыми моделями
- Изоляция исполнения (Subprocess-Smoke): запрет in-process импорта, тестирование через subprocess
- Допуск по хэшу (Hash-Bound Admission): защита от несанкционированных изменений
- Продуктовая система метрик качества: Autonomy Rate, Число ложных SUCCESS, LLM Call Budget
- CodeCandidateSchema: схема для кандидатов кода с хэшем и статусом допуска
- AdmissionGate: класс для допуска кандидатов через smoke-test и валидацию хэша
- HashBoundSchema: схема для подписанных ресурсов с хэшем и статусом BLOCKED
- Таблица quality_metrics: метрики качества разработки в SQLite
- Раздел "Безопасность" с описанием изоляции исполнения
- Раздел "Метрики" с описанием трех численных метрик качества

### v1.8 (2026-09-20)
- Добавлен модуль интерактивного обучения: Живая Онтология Девиаций (expert_teacher.py)
- Human-in-the-loop Grounding: Заземление через человека без Fine-Tuning
- Динамические Пространства Контекста (Contextual Ontologies) вместо жестких IF-THEN цепочек
- Механизм контекстного сита (Semantic Overlay): гравитационные поля вокруг базовых концепций
- Few-Shot RAG: семантическая маска прошлых уроков на новые спецификации
- Кристаллизация Онтологии (Ontology Distillation): Devin AI Assistant обобщает уроки в эвристические чек-листы
- ExpertLessonSchema: context_tags, raw_page_text, expert_commentary, applicability_scope
- ExpertTeacher: модуль для создания уроков, семантического поиска, кластеризации
- Таблица expert_lessons в SQLite + ChromaDB коллекция для экспертных уроков
- Фаза 10: Jobs для интерактивного обучения (#31-#33)
- Job #31: ExpertTeacher - Базовая инфраструктура
- Job #32: ExpertTeacher - Semantic Overlay и Few-Shot RAG
- Job #33: ExpertTeacher - Кристаллизация Онтологии (Devin + qwen2.5:14b)

### v1.7 (2026-09-20)
- Добавлены архитектурные решения от Google AI v7 - Исправление схем и Jobs для слабых LLM
- ConstraintSchema: добавлено поле severity_level (CRITICAL, MAJOR, MINOR) для цены нарушения ограничений
- ConstraintSchema: добавлен флаг bypass_strict_rule для "Пакта о помилования" от Метода 3
- DelegatedQuestionSchema: добавлены поля deadline_for_reply, reminder_count для эскалации зависших вопросов
- DelegatedQuestionSchema: добавлены поля escalation_status, escalated_to_user_id, escalation_timestamp
- Контур Консенсуса: Метод 3 может накладывать BYPASS_STRICT_RULE на детерминированные проверки Метода 1
- Эскалация зависших вопросов: мягкое напоминание через 4 часа, эскалация пользователю через 24 часа
- Порядок Jobs для слабых LLM: 30 Jobs в 9 фазах (инфраструктура, точность, ограничения, риск, время, делегация, документы, RAG, интеграция)
- Job #1-#5: Базовая инфраструктура (схемы, SQLite, DiaryManager, ChromaDB, Ollama)
- Job #6-#9: Контур точности (NetworkX, RAG, Telegram, Консенсус-Арбитр)
- Job #10-#12: Управление ограничениями (ConstraintManager, IntentClassifier, NegativeEventTrigger)
- Job #13-#14: Кумулятивный риск (HealthScoreEngine, интеграция с ограничениями)
- Job #15-#17: Темпоральная логика (TemporalLogicManager, AlertDispatcher, интеграция)
- Job #18-#20: Динамическая делегация (DelegationEngine, RoleRouterManager, интеграция)
- Job #21-#24: Документы и связывание (DocumentLinker, InboxManager, VirtualDocumentsManager, TelegramDistiller)
- Job #25-#27: RAG и поиск (поиск внутри объекта, между объектами, SQL-based финансы)
- Job #28-#30: Интеграция и мониторинг (мониторинг папки, миграция объектов, метрики)

### v1.5 (2026-09-20)
- Добавлены архитектурные решения от Google AI v5 - Темпоральная логика и динамическая делегация
- Absolute Time Injection: инъекция абсолютного времени в промпт, относительные переводы (Сегодня/Завтра/Вчера)
- Deternministic time parsing: LLM парсит фразу → JSON, бэкенд математически вычисляет абсолютную дату
- Cron tasks в SQLite: таблица cron_tasks с фиксированными датами выполнения
- Диспетчер Алертов: APScheduler, регулярные напоминания (10:00), критические тревоги (16:00)
- Паттерн «Спроси у Светы»: граф ролей в SQLite, контекстный парсинг имен, выбор канала связи
- Перехват ответа: таблица delegated_questions со статусом AWAITING_REPLY, mistral:7b парсит ответы
- Многозначность имен: Human-in-the-loop при нескольких совпадениях, инлайн-кнопки выбора
- Изменение дедлайнов «задним числом»: статус PROLONGED_BY_CHAT, снижение критичности алерта до желтого
- TemporalLogicManager: контур темпоральной логики для корректной интерпретации времени
- AlertDispatcher: диспетчер алертов для проактивных уведомлений в рабочее время
- DelegationEngine: паттерн динамической делегации с переадресацией вопросов
- TemporalContextSchema: схема темпорального контекста с абсолютным временем и относительными переводами
- DelegationRequestSchema: схема запроса делегирования с контекстом вопроса
- DelegatedQuestionSchema: схема делегированного вопроса с каналом связи и статусом ответа

### v1.4 (2026-09-20)
- Добавлены архитектурные решения от Google AI v4 - Контур точности и независимые контуры
- Контур точности: тройной перекрестный аудит (NetworkX + RAG + Ollama 14B) для предотвращения галлюцинаций
- Адресный Human-in-the-loop: матрица компетенций ролей (system_roles), умная маршрутизация вопросов
- Shadow Document pattern: учет фантомных (отсутствующих) документов с жизненным циклом объекта
- Event Distiller pattern: агрегация Telegram-каналов без скриптинга (regex + LLM summary)
- SQL-based финансовые запросы: детерминированные SQL-запросы вместо LLM-суммирования для точности
- Модели Ollama под RTX 5060 16Gb: mistral:7b Q8 (классификация), qwen2.5:14b Q4 (анализ связей), nomic-embed-text (эмбеддинги)
- Rate limiting: asyncio.Semaphore(1) для монопольного доступа, параллельный CPU-bound парсинг
- Tenacity retry policy: экспоненциальный бэккофф для Ollama ошибок
- SHA-256 кэширование: экономия GPU при перезапусках миграции
- Threaded Timelines: сворачиваемые цепочки вместо линейного таймлайна (хаотический граф процессов)
- Local Knowledge Graph: vis.js или Cytoscape.js вокруг выбранного объекта
- Autonomy Rate метрика: целевой показатель >80% для качества автоматического связывания
- Shadow Deploy A/B тестирование: теневой пайплайн с ab_test_logs таблицей

### v1.3 (2026-09-20)
- Добавлены детальные технические решения от Google AI v3 (RTX 5060 16Gb оптимизация)
- Confidence threshold: динамический двухуровневый (0.90, 0.70)
- RAG метаданные: расширенный набор полей (doc_id, chunk_index, legal_entities)
- RAG приоритизация: Reciprocal Rank Fusion (RRF) с весами по типам документов
- Асинхронный LLM-пайплайн: Producer-Consumer на базе asyncio.Queue с семафорами
- Knowledge Graph: таблицы entities и object_edges для связей между объектами
- Inbox: таблица pending_links с поддержкой вебхуков/интерфейсов обратного вызова
- DocumentLinker: паттерн "Трубопровод" (Pipeline Interceptor)
- Цитаты: расширенные поля (citation_text, citation_page, citation_bbox, citation_confidence)
- Diff-визуализация: jsondiff + difflib с цветовой схемой и координатами для подсветки
- GUI временные шкалы: Storyline View с зумом до диаграммы Ганта
- Экспорт: Excel, PDF, JSON форматы
- Telegram: инлайн-кнопки с callback_data для Inbox
- APScheduler: ежедневный мониторинг в 02:00 ночи
- ChromaDB: единая коллекция с жесткой мета-фильтрацией
- Ollama: deepseek-coder:6.7b или llama3.1:8b с format="json"
- Отчеты валидации: реестр покрытия, аномалии, Confusion Matrix
- Обновление confidence scores: только при новых доп. соглашениях или обновлении модели
- Конфликтующие цитаты: статус CONFLICT и отправка в Inbox

### v1.2 (2026-09-20)
- Добавлены детальные технические решения от Google AI v2
- Confidence threshold: динамический двухуровневый (0.90, 0.70)
- RAG метаданные: расширенный набор полей (doc_id, chunk_index, legal_entities)
- RAG приоритизация: Reciprocal Rank Fusion (RRF) с весами по типам документов
- Асинхронный LLM-пайплайн: Producer-Consumer на базе asyncio.Queue с семафорами
- Knowledge Graph: таблицы entities и object_edges для связей между объектами
- Inbox: таблица pending_links с поддержкой вебхуков/интерфейсов обратного вызова
- DocumentLinker: паттерн "Трубопровод" (Pipeline Interceptor)
- Цитаты: расширенные поля (citation_text, citation_page, citation_bbox, citation_confidence)
- Diff-визуализация: jsondiff + difflib с цветовой схемой и координатами для подсветки
- GUI временные шкалы: Storyline View с зумом до диаграммы Ганта
- Экспорт: Excel, PDF, JSON форматы
- Telegram: инлайн-кнопки с callback_data для Inbox
- APScheduler: ежедневный мониторинг в 02:00 ночи
- ChromaDB: единая коллекция с жесткой мета-фильтрацией
- Ollama: deepseek-coder:6.7b или llama3.1:8b с format="json"
- Отчеты валидации: реестр покрытия, аномалии, Confusion Matrix
- Обновление confidence scores: только при новых доп. соглашениях или обновлении модели
- Конфликтующие цитаты: статус CONFLICT и отправка в Inbox

### v1.1 (2026-09-20)
- Добавлены архитектурные решения от Google AI
- RAG: гибридный подход с единой коллекцией и жестким мета-фильтрованием
- Поиск между объектами: двухуровневый подход (RAG + Knowledge Graph)
- Ошибки связывания: Human-in-the-loop через Inbox с confidence threshold 0.85
- DocumentLinker: отдельный изолированный модуль для связывания документов
- Справочная ветка: object_id = "GLOBAL_REFERENCE" в основной таблице
- Миграция существующих объектов: 3-этапный подход (детерминированный + LLM + валидация)
- Защита от галлюцинаций: цитирование строк из текста для сумм и дат
- Версионирование документов: частичные изменения через Event-сущность

### v1.0 (2026-09-20)
- Initial version
- Основные требования определены
- Архитектура предложена
- План реализации составлен
