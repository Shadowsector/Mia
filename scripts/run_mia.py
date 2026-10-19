"""Main entry point for Mia PM OS with local Ollama - RFC v1.9"""

import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.modules.llm.ollama_client import OllamaClient
from app.modules.rag.chroma_manager import ChromaManager
from app.modules.object_diary.diary_manager import DiaryManager
from app.modules.object_diary.constraint_manager import ConstraintManager
from app.modules.object_diary.health_score_engine import HealthScoreEngine
from app.modules.object_diary.temporal_logic import TemporalLogic
from app.modules.object_diary.alert_dispatcher import AlertDispatcher
from app.modules.object_diary.constraint_health_integration import ConstraintHealthIntegration
from app.modules.delegation.delegation_engine import DelegationEngine
from app.modules.accuracy.accuracy_contour import AccuracyContourManager


class MiaSystem:
    """Основной класс системы Mia PM OS"""
    
    def __init__(self):
        print("🚀 Инициализация Mia PM OS - RFC v1.9")
        print("=" * 60)
        
        # Инициализация компонентов
        print("\n🔧 Инициализация компонентов...")
        
        # LLM Client
        print("  - Ollama Client...")
        self.ollama_client = OllamaClient(base_url="http://localhost:11434")
        
        # RAG
        print("  - ChromaDB Manager...")
        self.chroma_manager = ChromaManager(persist_directory="./chroma_db")
        
        # Object Diary
        print("  - Diary Manager...")
        self.diary_manager = DiaryManager()
        
        print("  - Constraint Manager...")
        self.constraint_manager = ConstraintManager()
        
        print("  - Health Score Engine...")
        self.health_engine = HealthScoreEngine()
        
        # Temporal
        print("  - Temporal Logic Manager...")
        self.temporal_manager = TemporalLogic()
        
        print("  - Alert Dispatcher...")
        self.alert_dispatcher = AlertDispatcher()
        
        print("  - Temporal-Alert Integration...")
        self.temporal_alert_integration = TemporalAlertIntegration()
        
        # Delegation
        print("  - Delegation Engine...")
        self.delegation_engine = DelegationEngine()
        
        # Accuracy
        print("  - Accuracy Contour Manager...")
        self.accuracy_manager = AccuracyContourManager()
        
        print("\n✅ Все компоненты инициализированы")
        print("=" * 60)
    
    async def start(self):
        """Запустить систему"""
        print("\n🚀 Запуск Mia PM OS...")
        
        # Запуск планировщика алертов
        print("  - Запуск Alert Dispatcher...")
        self.alert_dispatcher.start()
        
        # Запуск темпоральной интеграции
        print("  - Запуск Temporal-Alert Integration...")
        self.temporal_alert_integration.start()
        
        print("\n✅ Система запущена")
        print("=" * 60)
        print("\nДоступные компоненты:")
        print("  - self.ollama_client: Генерация текста и JSON")
        print("  - self.chroma_manager: RAG и поиск")
        print("  - self.diary_manager: Управление дневниками")
        print("  - self.constraint_manager: Управление ограничениями")
        print("  - self.health_engine: Расчет Health Score")
        print("  - self.temporal_manager: Темпоральная логика")
        print("  - self.alert_dispatcher: Отправка алертов")
        print("  - self.delegation_engine: Делегирование вопросов")
        print("  - self.accuracy_manager: Контур точности")
        print("\nПример использования:")
        print("  system = MiaSystem()")
        print("  await system.start()")
        print("  system.diary_manager.create_diary(...)")
        print("=" * 60)
    
    async def stop(self):
        """Остановить систему"""
        print("\n🛑 Остановка Mia PM OS...")
        
        self.alert_dispatcher.stop()
        self.temporal_alert_integration.stop()
        
        print("✅ Система остановлена")
    
    def get_system_status(self) -> dict:
        """Получить статус системы"""
        return {
            "ollama_connected": self._check_ollama(),
            "chroma_stats": self.chroma_manager.get_collection_stats(),
            "total_diaries": len(self.diary_manager.get_all_diaries()),
            "scheduler_running": self.alert_dispatcher.scheduler.running
        }
    
    def _check_ollama(self) -> bool:
        """Проверить соединение с Ollama"""
        try:
            self.ollama_client.client.list()
            return True
        except:
            return False


async def main():
    """Главная функция"""
    
    print("\n" + "=" * 60)
    print("Mia PM OS - Construction Project Management System")
    print("RFC v1.9 - Object Diary System")
    print("=" * 60)
    
    # Создание системы
    system = MiaSystem()
    
    # Запуск
    await system.start()
    
    # Статус
    status = system.get_system_status()
    print("\n📊 Статус системы:")
    print(f"  Ollama: {'✅ Подключен' if status['ollama_connected'] else '❌ Не подключен'}")
    print(f"  ChromaDB чанков: {status['chroma_stats']['total_chunks']}")
    print(f"  Дневников: {status['total_diaries']}")
    print(f"  Планировщик: {'✅ Запущен' if status['scheduler_running'] else '❌ Остановлен'}")
    
    print("\n💡 Для интерактивного режима:")
    print("  from scripts.run_mia import system")
    print("  system.diary_manager.create_diary(...)")
    
    # Остановка (в реальном использовании система будет работать вечно)
    # await system.stop()


if __name__ == "__main__":
    asyncio.run(main())
