# 🚀 Запуск Mia PM OS с локальным Ollama

## Предварительные требования

1. **Ollama** - скачайте с https://ollama.com/download и установите для Windows
2. **Python 3.9+** - система уже настроена
3. **RTX 5060 16Gb** - для локального инференса

## Шаг 1: Настройка Ollama

### Запуск Ollama Server
Откройте терминал и запустите:
```bash
ollama serve
```

### Загрузка моделей
В другом терминале запустите скрипт настройки:
```bash
cd C:\mia
python scripts\setup_ollama.py
```

Этот скрипт загрузит модели по RFC v1.9:
- `mistral:7b-instruct-v0.3` - для классификации
- `qwen2.5:14b-instruct-q4_K_M` - для анализа связей
- `nomic-embed-text` - для эмбеддингов

## Шаг 2: Инициализация базы данных

База данных инициализируется автоматически при первом запуске.

```bash
python -c "from app.modules.storage.database import initialize_database; initialize_database()"
```

## Шаг 3: Тестирование интеграции

Запустите интеграционные тесты:
```bash
python scripts\test_integration.py
```

Тесты проверяют:
- ✅ Соединение с Ollama
- ✅ Генерацию текста и JSON
- ✅ Генерацию embeddings
- ✅ Темпоральный контекст
- ✅ ChromaDB (RAG)
- ✅ Diary Manager

## Шаг 4: Запуск системы

### Режим запуска
```bash
python scripts\run_mia.py
```

### Интерактивный режим
```python
from scripts.run_mia import MiaSystem
import asyncio

async def main():
    system = MiaSystem()
    await system.start()
    
    # Использование компонентов
    from app.core.schemas import ObjectDiarySchema
    from datetime import datetime
    
    diary_data = ObjectDiarySchema(
        object_name="Судакова",
        object_id="folder_id_123",
        customer="Спецэкосервис",
        contract_date=datetime.now(),
        contract_amount=5000000.0
    )
    
    diary_id = system.diary_manager.create_diary(diary_data)
    print(f"Дневник создан: {diary_id}")

asyncio.run(main())
```

## 📊 Реализованные модули (RFC v1.9)

### Базовая инфраструктура
- ✅ `app/core/schemas.py` - все Pydantic схемы
- ✅ `app/modules/storage/database.py` - 14 новых таблиц
- ✅ `app/modules/llm/ollama_client.py` - Ollama клиент с кэшированием
- ✅ `app/modules/rag/chroma_manager.py` - ChromaDB с RRF

### Object Diary
- ✅ `app/modules/object_diary/diary_manager.py` - CRUD, версии, цитирование
- ✅ `app/modules/object_diary/constraint_manager.py` - Сеть ограничений
- ✅ `app/modules/object_diary/intent_classifier.py` - Классификация намерений
- ✅ `app/modules/object_diary/negative_event_trigger.py` - Триггеры на молчание
- ✅ `app/modules/object_diary/health_score_engine.py` - Кумулятивный риск
- ✅ `app/modules/object_diary/constraint_health_integration.py` - Интеграция

### Темпоральная логика
- ✅ `app/modules/temporal/temporal_logic.py` - Absolute Time Injection
- ✅ `app/modules/temporal/alert_dispatcher.py` - APScheduler алерты
- ✅ `app/modules/temporal/temporal_alert_integration.py` - Интеграция

### Делегирование
- ✅ `app/modules/delegation/delegation_engine.py` - Спроси у Светы

### Контур точности
- ✅ `app/modules/accuracy/accuracy_contour.py` - Тройной аудит (NetworkX + RAG + Telegram)

## 🔧 Конфигурация

### Модели Ollama
В `app/modules/llm/ollama_client.py`:
```python
self.models = {
    "classification": "mistral:7b-instruct-v0.3",
    "analysis": "qwen2.5:14b-instruct-q4_K_M",
    "embedding": "nomic-embed-text"
}
```

### Бюджет токенов
```python
self.max_tokens_per_request = 4000
self.max_time_per_request = 30  # seconds
```

### Рабочее время алертов
В `app/modules/temporal/alert_dispatcher.py`:
```python
self.working_hours_start = time(9, 0)  # 09:00
self.working_hours_end = time(18, 0)   # 18:00
```

## 📝 Примеры использования

### Создание дневника объекта
```python
from app.modules.object_diary.diary_manager import DiaryManager
from app.core.schemas import ObjectDiarySchema
from datetime import datetime

manager = DiaryManager()

diary = ObjectDiarySchema(
    object_name="Судакова",
    object_id="1AbCdEfGhIjKlMnOpQrStUvWxYz",
    customer="Спецэкосервис (СЭС)",
    contract_date=datetime(2026, 9, 20),
    contract_amount=5000000.0
)

diary_id = manager.create_diary(diary)
```

### Добавление события с цитированием
```python
from app.core.schemas import DiaryEventSchema

event = DiaryEventSchema(
    event_type="contract_created",
    event_timestamp=datetime.now(),
    entity_type="document",
    entity_id="doc_123",
    summary="Договор №123 создан",
    citation_text="Договор №123 от 20.09.2026 на сумму 5 000 000 руб",
    citation_page=1,
    citation_confidence=0.95
)

event_id = manager.add_event(diary_id, event)
```

### Проверка ограничений
```python
from app.modules.object_diary.constraint_manager import ConstraintManager

constraint_manager = ConstraintManager()

constraint_id = constraint_manager.create_constraint(
    object_id="1AbCdEfGhIjKlMnOpQrStUvWxYz",
    constraint_type="OATI_NOTIFICATION",
    constraint_name="Уведомление ОАТИ",
    description="Уведомление ОАТИ за 7 дней до земляных работ",
    required_for_actions=["earthworks"],
    severity_level="CRITICAL"
)

result = constraint_manager.check_constraints_for_action(
    object_id="1AbCdEfGhIjKlMnOpQrStUvWxYz",
    action="earthworks"
)

if result.can_proceed:
    print("Можно продолжать")
else:
    print(f"Заблокировано: {result.blocking_constraints}")
```

### Расчет Health Score
```python
from app.modules.object_diary.health_score_engine import HealthScoreEngine

health_engine = HealthScoreEngine()

health_score = health_engine.calculate_health_score(
    object_id="1AbCdEfGhIjKlMnOpQrStUvWxYz"
)

print(f"Health Score: {health_score.score}")
print(f"Zone: {health_score.zone}")
print(f"Risk Factors: {health_score.risk_factors}")
```

### Темпоральный контекст
```python
from app.modules.temporal.temporal_logic import TemporalLogicManager

temporal_manager = TemporalLogicManager()

context = temporal_manager.get_temporal_context()
print(f"Сегодня: {context.relative_translation_map['Сегодня']}")
print(f"Завтра: {context.relative_translation_map['Завтра']}")

# Разрешение относительной даты
absolute_date = temporal_manager.resolve_relative_date("через неделю")
print(f"Через неделю: {absolute_date}")
```

## 🐛 Устранение проблем

### Ollama не запущен
```
❌ Ошибка соединения с Ollama
```
Решение: Запустите `ollama serve` в отдельном терминале

### Модель не загружена
```
❌ Модель mistral:7b-instruct-v0.3 не найдена
```
Решение: Запустите `python scripts\setup_ollama.py`

### VRAM переполнение
```
❌ CUDA out of memory
```
Решение: Код уже имеет защиту через `asyncio.Semaphore(1)` и ограничение токенов

## 📚 Следующие шаги

1. Запустите `setup_ollama.py` для загрузки моделей
2. Запустите `test_integration.py` для проверки
3. Запустите `run_mia.py` для старта системы
4. Интегрируйте с существующими модулями (Telegram, Google Drive)
5. Мигрируйте 108 существующих объектов

## 🎯 Статус реализации

- ✅ RFC v1.9 полностью реализован
- ✅ Все 10 фаз завершены
- ✅ Паттерны надежности добавлены
- ✅ Модули готовы к интеграции
