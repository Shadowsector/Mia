"""Setup script for Ollama with required models for Mia - RFC v1.9"""

import subprocess
import sys
import time


def check_ollama_installed():
    """Проверить, установлен ли Ollama"""
    try:
        result = subprocess.run(
            ["ollama", "version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print(f"✅ Ollama установлен: {result.stdout.strip()}")
            return True
        else:
            print("❌ Ollama не найден")
            return False
    except FileNotFoundError:
        print("❌ Ollama не установлен")
        print("Установите Ollama с https://ollama.com/download")
        return False
    except Exception as e:
        print(f"❌ Ошибка проверки Ollama: {e}")
        return False


def pull_model(model_name: str):
    """Загрузить модель из Ollama"""
    print(f"\n📥 Загрузка модели: {model_name}")
    try:
        process = subprocess.Popen(
            ["ollama", "pull", model_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        for line in process.stdout:
            print(line, end='')
        
        process.wait()
        
        if process.returncode == 0:
            print(f"✅ Модель {model_name} загружена")
            return True
        else:
            print(f"❌ Ошибка загрузки {model_name}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def setup_ollama():
    """Настроить Ollama с требуемыми моделями по RFC v1.9"""
    
    print("=" * 60)
    print("Настройка Ollama для Mia PM OS - RFC v1.9")
    print("=" * 60)
    
    # Проверка установки
    if not check_ollama_installed():
        print("\nПожалуйста, установите Ollama:")
        print("1. Скачайте с https://ollama.com/download")
        print("2. Установите для Windows")
        print("3. Запустите эту команду снова")
        return False
    
    # Модели по RFC v1.9
    models = [
        "mistral:7b-instruct-v0.3",  # Классификация
        "qwen2.5:14b-instruct-q4_K_M",  # Анализ связей
        "nomic-embed-text"  # Эмбеддинги
    ]
    
    print(f"\nБудут загружены {len(models)} моделей:")
    for model in models:
        print(f"  - {model}")
    
    input("\nНажмите Enter для продолжения...")
    
    # Загрузка моделей
    success_count = 0
    for model in models:
        if pull_model(model):
            success_count += 1
        time.sleep(2)  # Пауза между загрузками
    
    print("\n" + "=" * 60)
    print(f"Загружено {success_count}/{len(models)} моделей")
    print("=" * 60)
    
    if success_count == len(models):
        print("✅ Все модели загружены успешно!")
        print("Теперь можно запускать Mia с локальным Ollama")
        return True
    else:
        print("⚠️ Некоторые модели не загружены")
        return False


if __name__ == "__main__":
    setup_ollama()
