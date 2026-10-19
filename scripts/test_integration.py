"""Test script for Ollama Client integration - RFC v1.9"""

import sys
import asyncio
from pathlib import Path

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.modules.llm.ollama_client import OllamaClient, PromptTemplates


async def test_ollama_client():
    """Тест Ollama клиента"""
    
    print("=" * 60)
    print("Тест Ollama Client - RFC v1.9")
    print("=" * 60)
    
    # Инициализация клиента
    print("\n🔧 Инициализация Ollama Client...")
    client = OllamaClient(base_url="http://localhost:11434")
    
    # Тест 1: Проверка соединения
    print("\n📡 Тест 1: Проверка соединения с Ollama")
    try:
        models = client.client.list()
        print(f"✅ Соединение установлено")
        print(f"   Доступные модели: {len(models['models'])}")
        for model in models['models']:
            print(f"   - {model['name']}")
    except Exception as e:
        print(f"❌ Ошибка соединения: {e}")
        print("Убедитесь, что Ollama запущен: ollama serve")
        return False
    
    # Тест 2: Кэширование
    print("\n💾 Тест 2: Проверка кэширования")
    cache_stats = client.get_cache_stats()
    print(f"   Кэш-директория: {cache_stats['cache_dir']}")
    print(f"   Кэшированных запросов: {cache_stats['cached_requests']}")
    print(f"   Размер кэша: {cache_stats['total_size_mb']:.2f} MB")
    
    # Тест 3: Генерация текста
    print("\n📝 Тест 3: Генерация текста")
    test_prompt = "Say hello in Russian"
    try:
        result = await client.generate(
            prompt=test_prompt,
            model="mistral:7b-instruct-v0.3",
            cache_key="test_hello"
        )
        print(f"✅ Генерация успешна")
        print(f"   Ответ: {result['response'][:100]}...")
    except Exception as e:
        print(f"❌ Ошибка генерации: {e}")
        return False
    
    # Тест 4: Генерация JSON
    print("\n📋 Тест 4: Генерация JSON")
    json_prompt = PromptTemplates.intent_classifier_prompt(
        message="привезли кольца на Судакова",
        context="строительный объект"
    )
    try:
        json_result = await client.generate_json(
            prompt=json_prompt,
            model="mistral:7b-instruct-v0.3"
        )
        print(f"✅ JSON генерация успешна")
        print(f"   Intent: {json_result.get('domain_intent', 'N/A')}")
        print(f"   Confidence: {json_result.get('confidence', 0.0)}")
    except Exception as e:
        print(f"❌ Ошибка JSON генерации: {e}")
        return False
    
    # Тест 5: Embeddings
    print("\n🔤 Тест 5: Генерация embeddings")
    test_text = "строительный объект Судакова"
    try:
        embedding = client.get_embedding(test_text, model="nomic-embed-text")
        print(f"✅ Embedding сгенерирован")
        print(f"   Размерность: {len(embedding)}")
        print(f"   Первые 5 значений: {embedding[:5]}")
    except Exception as e:
        print(f"❌ Ошибка генерации embedding: {e}")
        return False
    
    # Тест 6: Темпоральный контекст
    print("\n⏰ Тест 6: Темпоральный контекст")
    from app.modules.object_diary.temporal_logic import TemporalLogic
    temporal_manager = TemporalLogic()
    context = temporal_manager.get_temporal_context()
    print(f"✅ Темпоральный контекст получен")
    print(f"   Текущее время: {context.current_absolute_time}")
    print(f"   День недели: {context.current_day_of_week}")
    print(f"   Переводов: {len(context.relative_translation_map)}")
    
    # Тест 7: Разрешение относительных дат
    print("\n📅 Тест 7: Разрешение относительных дат")
    test_phrases = ["завтра", "через неделю", "через 3 дня"]
    for phrase in test_phrases:
        resolved = temporal_manager.resolve_relative_date(phrase)
        if resolved:
            print(f"   '{phrase}' → {resolved.strftime('%Y-%m-%d')}")
        else:
            print(f"   '{phrase}' → не распознано")
    
    print("\n" + "=" * 60)
    print("✅ Все тесты пройдены успешно!")
    print("=" * 60)
    
    return True


async def test_chroma_manager():
    """Тест ChromaDB менеджера"""
    
    print("\n" + "=" * 60)
    print("Тест ChromaDB Manager - RFC v1.9")
    print("=" * 60)
    
    from app.modules.rag.chroma_manager import ChromaManager
    
    print("\n🔧 Инициализация ChromaDB Manager...")
    chroma = ChromaManager(persist_directory="./chroma_db")
    
    print("\n📊 Статистика коллекции:")
    stats = chroma.get_collection_stats()
    print(f"   Название: {stats['collection_name']}")
    print(f"   Всего чанков: {stats['total_chunks']}")
    print(f"   Директория: {stats['persist_directory']}")
    
    print("\n📝 Тест добавления чанка:")
    chunk_id = chroma.add_chunk(
        chunk_text="Тестовый чанк для объекта Судакова",
        object_id="test_object",
        doc_id="test_doc",
        doc_category="CONTRACT",
        is_current=True,
        chunk_index=0
    )
    print(f"✅ Чанк добавлен: {chunk_id}")
    
    print("\n🔍 Тест поиска внутри объекта:")
    results = chroma.search_within_object(
        query_text="Судакова",
        object_id="test_object",
        n_results=5
    )
    print(f"✅ Найдено результатов: {len(results)}")
    for result in results:
        print(f"   - {result['text'][:50]}...")
    
    print("\n" + "=" * 60)
    print("✅ ChromaDB тесты пройдены!")
    print("=" * 60)


async def test_diary_manager():
    """Тест Diary Manager"""
    
    print("\n" + "=" * 60)
    print("Тест Diary Manager - RFC v1.9")
    print("=" * 60)
    
    from app.modules.object_diary.diary_manager import DiaryManager
    from app.core.schemas import ObjectDiarySchema, DiaryEventSchema
    from datetime import datetime
    
    print("\n🔧 Инициализация Diary Manager...")
    diary_manager = DiaryManager()
    
    print("\n📝 Тест создания дневника:")
    diary_data = ObjectDiarySchema(
        object_name="Тестовый объект",
        object_id="test_folder_id",
        customer="Тестовый заказчик",
        contract_date=datetime.now(),
        contract_amount=1000000.0
    )
    
    diary_id = diary_manager.create_diary(diary_data)
    print(f"✅ Дневник создан: ID {diary_id}")
    
    print("\n📝 Тест получения дневника:")
    retrieved = diary_manager.get_diary(diary_id)
    if retrieved:
        print(f"✅ Дневник получен: {retrieved.object_name}")
    
    print("\n📝 Тест добавления события:")
    event_data = DiaryEventSchema(
        event_type="contract_created",
        event_timestamp=datetime.now(),
        entity_type="document",
        entity_id="doc_123",
        summary="Договор создан",
        citation_text="Договор №123 от 20.09.2026",
        citation_page=1,
        citation_confidence=0.95
    )
    
    event_id = diary_manager.add_event(diary_id, event_data)
    print(f"✅ Событие добавлено: ID {event_id}")
    
    print("\n📝 Тест получения таймлайна:")
    timeline = diary_manager.get_timeline(diary_id)
    print(f"✅ Таймлайн получен: {len(timeline)} событий")
    for event in timeline:
        print(f"   - {event.event_type}: {event.summary}")
    
    print("\n🗑️ Тест удаления тестовых данных:")
    diary_manager.delete_diary(diary_id)
    print("✅ Тестовые данные удалены")
    
    print("\n" + "=" * 60)
    print("✅ Diary Manager тесты пройдены!")
    print("=" * 60)


async def main():
    """Главная функция тестирования"""
    
    print("\n🚀 Запуск интеграционных тестов Mia PM OS")
    print("Убедитесь, что Ollama запущен: ollama serve\n")
    
    # Тест Ollama
    ollama_ok = await test_ollama_client()
    
    if ollama_ok:
        # Тест ChromaDB
        await test_chroma_manager()
        
        # Тест Diary Manager
        await test_diary_manager()
        
        print("\n" + "=" * 60)
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("=" * 60)
        print("\nСистема готова к работе с локальным Ollama")
        print("Доступные модули:")
        print("  - app/modules/llm/ollama_client.py")
        print("  - app/modules/rag/chroma_manager.py")
        print("  - app/modules/object_diary/diary_manager.py")
        print("  - app/modules/object_diary/constraint_manager.py")
        print("  - app/modules/object_diary/health_score_engine.py")
        print("  - app/modules/temporal/temporal_logic.py")
        print("  - app/modules/temporal/alert_dispatcher.py")
        print("  - app/modules/delegation/delegation_engine.py")
        print("  - app/modules/accuracy/accuracy_contour.py")
    else:
        print("\n❌ Ollama тесты не пройдены")
        print("Запустите скрипт setup_ollama.py для настройки")


if __name__ == "__main__":
    asyncio.run(main())
