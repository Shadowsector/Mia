"""Simple Mia PM OS Controller for non-technical users"""

import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mia_system.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class MiaController:
    """Simple controller for Mia PM OS testing."""
    
    def __init__(self):
        self.is_running = False
        self.start_time = None
        self.tasks_completed = 0
        self.errors = 0
        
    def start_system(self):
        """Start Mia system components."""
        if self.is_running:
            print("❌ Система уже запущена!")
            return False
        
        print("🚀 Запуск Mia PM OS...")
        
        try:
            # 1. Initialize database
            print("📦 Инициализация базы данных...")
            from app.modules.storage.database import initialize_database
            initialize_database()
            print("✅ База данных инициализирована")
            
            # 2. Initialize questions gateway
            print("❓ Инициализация Questions Gateway...")
            from app.modules.storage.questions_gateway import initialize_questions_database
            initialize_questions_database()
            print("✅ Questions Gateway готов")
            
            # 3. Initialize audit system
            print("🔍 Инициализация Audit Vector...")
            from app.workers.audit_vector import initialize_audit_database
            initialize_audit_database()
            print("✅ Audit Vector готов")
            
            # 4. Initialize doctor observer
            print("👨‍⚕️ Инициализация Doctor Observer...")
            from app.modules.doctor.observer import initialize_doctor_database
            initialize_doctor_database()
            print("✅ Doctor Observer готов")
            
            # 5. Start worker pool
            print("⚙️ Запуск Worker Pool...")
            from app.workers.worker_pool import SingleThreadedWorkerPool
            from app.modules.storage.questions_gateway import QuestionsGateway
            
            # Create simple task handler
            def simple_task_handler(task):
                logger.info(f"Processing task: {task['task_id']}")
                time.sleep(1)  # Simulate processing
                return {"status": "success", "task_id": task['task_id']}
            
            # Create questions gateway
            questions_gateway = QuestionsGateway(Path(__file__).parent)
            
            # Create worker pool
            self.worker_pool = SingleThreadedWorkerPool(
                task_handler=simple_task_handler,
                max_concurrent_tasks=1,
                poll_interval=0.5,
                questions_gateway=questions_gateway
            )
            
            self.worker_pool.start()
            print("✅ Worker Pool запущен")
            
            self.is_running = True
            self.start_time = datetime.now()
            
            print(f"🎉 Mia PM OS успешно запущена в {self.start_time.strftime('%H:%M:%S')}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка запуска: {e}")
            logger.error(f"System startup failed: {e}")
            return False
    
    def stop_system(self):
        """Stop Mia system components."""
        if not self.is_running:
            print("❌ Система не запущена!")
            return False
        
        print("🛑 Остановка Mia PM OS...")
        
        try:
            # Stop worker pool
            if hasattr(self, 'worker_pool'):
                self.worker_pool.stop()
                print("✅ Worker Pool остановлен")
            
            self.is_running = False
            runtime = datetime.now() - self.start_time if self.start_time else "неизвестно"
            
            print(f"🏁 Mia PM OS остановлена. Время работы: {runtime}")
            print(f"📊 Задач выполнено: {self.tasks_completed}")
            print(f"⚠️ Ошибок: {self.errors}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка остановки: {e}")
            logger.error(f"System shutdown failed: {e}")
            return False
    
    def get_status(self):
        """Get current system status."""
        if not self.is_running:
            print("📊 Статус: ⚪ НЕ ЗАПУЩЕНА")
            return
        
        try:
            print("📊 Статус Mia PM OS:")
            print(f"🟢 Состояние: ЗАПУЩЕНА")
            print(f"⏱️ Время работы: {datetime.now() - self.start_time if self.start_time else 'неизвестно'}")
            
            if hasattr(self, 'worker_pool'):
                worker_status = self.worker_pool.get_status()
                print(f"⚙️ Worker Pool: {worker_status['state']}")
                print(f"📝 Задач обработано: {worker_status['tasks_processed']}")
                print(f"❌ Задач с ошибками: {worker_status['tasks_failed']}")
                print(f"⏸️ Приостановлено задач: {worker_status.get('tasks_suspended', 0)}")
                
                queue_stats = worker_status.get('queue_statistics', {})
                print(f"📋 Очередь: {queue_stats.get('pending', 0)} ожидает, {queue_stats.get('processing', 0)} в обработке")
                
        except Exception as e:
            print(f"❌ Ошибка получения статуса: {e}")
    
    def show_logs(self, lines=20):
        """Show recent system logs."""
        print(f"📝 Последние {lines} строк логов:")
        print("-" * 50)
        
        try:
            with open('mia_system.log', 'r', encoding='utf-8') as f:
                log_lines = f.readlines()
                for line in log_lines[-lines:]:
                    print(line.strip())
        except FileNotFoundError:
            print("❌ Файл логов не найден")
        except Exception as e:
            print(f"❌ Ошибка чтения логов: {e}")
    
    def add_test_task(self):
        """Add a test task to the queue."""
        if not self.is_running:
            print("❌ Система не запущена!")
            return False
        
        try:
            from app.modules.storage.database import enqueue_task
            from datetime import datetime
            
            task_data = {
                'task_id': f"TEST-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'task_type': 'test_task',
                'priority': 8,
                'system_current_time': datetime.now(),
                'user_message': 'Тестовая задача для проверки Mia',
                'user_intent': 'test',
                'telegram_chat_id': -1001234567890,
                'user_id': 123456789
            }
            
            if enqueue_task(task_data):
                print(f"✅ Тестовая задача добавлена: {task_data['task_id']}")
                return True
            else:
                print("❌ Ошибка добавления задачи")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка создания задачи: {e}")
            return False
    
    def show_completed_tasks(self):
        """Show completed tasks from database."""
        print("📋 Завершённые задачи:")
        print("-" * 50)
        
        try:
            from app.modules.storage.database import get_db_connection
            
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT task_id, task_type, priority, status, completed_at, result
                    FROM llm_task_queue 
                    WHERE status = 'completed'
                    ORDER BY completed_at DESC 
                    LIMIT 10
                """)
                
                rows = cursor.fetchall()
                if not rows:
                    print("📭 Завершённых задач пока нет")
                    return
                
                for row in rows:
                    print(f"📝 {row['task_id']} ({row['task_type']})")
                    print(f"   Приоритет: {row['priority']}, Статус: {row['status']}")
                    print(f"   Завершено: {row['completed_at']}")
                    print(f"   Результат: {row['result'][:50] if row['result'] else 'N/A'}...")
                    print("-" * 30)
                    
        except Exception as e:
            print(f"❌ Ошибка получения задач: {e}")
    
    def show_queue_statistics(self):
        """Show queue statistics."""
        print("📊 Статистика очереди:")
        print("-" * 50)
        
        try:
            from app.modules.storage.database import get_queue_statistics
            
            stats = get_queue_statistics()
            print(f"⏳ Ожидающих задач: {stats['pending']}")
            print(f"⚙️ В обработке: {stats['processing']}")
            print(f"✅ Завершено: {stats['completed']}")
            print(f"❌ С ошибками: {stats['failed']}")
            
        except Exception as e:
            print(f"❌ Ошибка получения статистики: {e}")
    
    def test_questions_gateway(self):
        """Test Questions Gateway functionality."""
        print("❓ Тестирование Questions Gateway:")
        print("-" * 50)
        
        try:
            from app.modules.storage.questions_gateway import QuestionsGateway
            from datetime import datetime
            
            gateway = QuestionsGateway(Path(__file__).parent)
            
            # Create a test question
            question_data = {
                "question_id": f"Q-TEST-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "question_type": "test_question",
                "priority": "normal",
                "project_id": "PROJ-TEST-001",
                "related_schema_type": "TestSchema",
                "related_entity_id": "TEST-001",
                "question_markdown": "# Test Question\n\nThis is a test question for Mia.\n\n## Options:\n**(a)** Option A\n**(b)** Option B",
                "option_a": "Option A",
                "option_b": "Option B"
            }
            
            question_id = gateway.ask_human(question_data)
            print(f"✅ Тестовый вопрос создан: {question_id}")
            
            # Get open questions
            open_questions = gateway.get_open_questions()
            print(f"📋 Открытых вопросов: {len(open_questions)}")
            
            gateway.cleanup_shadow_copies()
            print("✅ Questions Gateway тест пройден")
            
        except Exception as e:
            print(f"❌ Ошибка тестирования Questions Gateway: {e}")
    
    def test_audit_vector(self):
        """Test Audit Vector functionality."""
        print("🔍 Тестирование Audit Vector:")
        print("-" * 50)
        
        try:
            from app.workers.audit_vector import NighttimeAuditVector
            
            audit_vector = NighttimeAuditVector(Path(__file__).parent)
            
            # Run a single audit cycle
            print("⚙️ Запуск аудита...")
            audit_vector._perform_audit_cycle()
            
            stats = audit_vector.get_audit_statistics()
            print(f"📊 Статистика аудита:")
            print(f"   Аудитов выполнено: {stats['audits_performed']}")
            print(f"   Гапов обнаружено: {stats['gaps_detected']}")
            print(f"   Критических гапов: {stats['critical_gaps']}")
            
            print("✅ Audit Vector тест пройден")
            
        except Exception as e:
            print(f"❌ Ошибка тестирования Audit Vector: {e}")
    
    def run_quick_test(self):
        """Run a quick comprehensive test."""
        print("🧪 Запуск комплексного теста Mia PM OS:")
        print("=" * 50)
        
        # 1. Start system
        if not self.start_system():
            print("❌ Тест провален: не удалось запустить систему")
            return False
        
        time.sleep(2)
        
        # 2. Add test tasks
        print("\n📝 Добавление тестовых задач...")
        for i in range(3):
            self.add_test_task()
            time.sleep(0.5)
        
        # 3. Wait for processing
        print("\n⏳ Ожидание обработки задач...")
        time.sleep(5)
        
        # 4. Check status
        print("\n📊 Проверка статуса...")
        self.get_status()
        
        # 5. Show completed tasks
        print("\n📋 Проверка завершённых задач...")
        self.show_completed_tasks()
        
        # 6. Stop system
        print("\n🛑 Остановка системы...")
        self.stop_system()
        
        print("\n✅ Комплексный тест завершён!")
        return True


def print_menu():
    """Print main menu."""
    print("\n" + "=" * 50)
    print("🏗️  Mia PM OS - Панель управления")
    print("=" * 50)
    print("1. 🚀 Запустить систему")
    print("2. 🛑 Остановить систему")
    print("3. 📊 Показать статус")
    print("4. 📝 Показать логи")
    print("5. ➕ Добавить тестовую задачу")
    print("6. 📋 Показать завершённые задачи")
    print("7. 📊 Статистика очереди")
    print("8. ❓ Тест Questions Gateway")
    print("9. 🔍 Тест Audit Vector")
    print("10. 🧪 Комплексный тест")
    print("0. 🚪 Выход")
    print("=" * 50)


def main():
    """Main function."""
    controller = MiaController()
    
    print("🎉 Добро пожаловать в Mia PM OS!")
    print("Система управления строительными проектами с AI")
    
    while True:
        print_menu()
        
        try:
            choice = input("👉 Выберите действие (0-10): ").strip()
            
            if choice == "1":
                controller.start_system()
            elif choice == "2":
                controller.stop_system()
            elif choice == "3":
                controller.get_status()
            elif choice == "4":
                controller.show_logs()
            elif choice == "5":
                controller.add_test_task()
            elif choice == "6":
                controller.show_completed_tasks()
            elif choice == "7":
                controller.show_queue_statistics()
            elif choice == "8":
                controller.test_questions_gateway()
            elif choice == "9":
                controller.test_audit_vector()
            elif choice == "10":
                controller.run_quick_test()
            elif choice == "0":
                print("👋 До свидания!")
                if controller.is_running:
                    print("⚠️ Система всё ещё запущена. Остановить её? (y/n)")
                    if input().lower() == 'y':
                        controller.stop_system()
                break
            else:
                print("❌ Неверный выбор. Попробуйте снова.")
                
        except KeyboardInterrupt:
            print("\n⚠️ Прерывание пользователем")
            if controller.is_running:
                controller.stop_system()
            break
        except Exception as e:
            print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    main()