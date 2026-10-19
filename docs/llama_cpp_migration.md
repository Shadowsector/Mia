# 🚀 Миграция на llama.cpp и Новый GUI

## ✅ Что сделано:

### 1. LlamaCppManager
- Создан модуль `app/modules/llm/llama_cpp_manager.py`
- Легче и быстрее чем Ollama для RTX 5060 16GB
- Автоматическое скачивание моделей с HuggingFace
- Поддержка стриминга

### 2. Новый GUI (Полный редизайн)
- Файл: `gui/mia_gui_redesigned.py`
- **Автозапуск llama.cpp** при старте
- **Нормальный чат** с полем ввода, кнопками Send/Clear
- **Copy-paste** работает в чате и поле ввода
- **Реалтайм Telegram чат** (заготовка)
- **Боковая панель** с быстрыми действиями
- **Логи** прямо в интерфейсе

### 3. Конфигурация
- Файл: `mia_config.json`
- Путь к llama-server.exe
- Путь к модели
- Настройки GPU слоёв, контекста, потоков

### 4. Ярлык на рабочем столе
- Скрипт: `create_shortcut.bat`
- Создаёт ярлык "Mia PM OS" на рабочем столе

## 📋 Инструкция по установке:

### Шаг 1: Установить llama.cpp

1. Скачайте релиз с: https://github.com/ggerganov/llama.cpp/releases
2. Распакуйте в `C:\llama.cpp\`
3. Убедитесь, что есть `llama-server.exe`

### Шаг 2: Скачать модель

Вариант 1: Автоматически через Python
```bash
cd C:\mia
python -c "from app.modules.llm.llama_cpp_manager import download_model; download_model('qwen2.5-14b-instruct-q4', './models')"
```

Вариант 2: Вручную с HuggingFace
- https://huggingface.co/Qwen/Qwen2.5-14B-Instruct-GGUF
- Скачайте `qwen2.5-14b-instruct-q4_k_m.gguf`
- Сохраните в `C:\models\`

### Шаг 3: Настроить конфигурацию

Откройте `mia_config.json` и проверьте пути:
```json
{
  "llama_cpp_path": "C:\\llama.cpp\\llama-server.exe",
  "model_path": "C:\\models\\qwen2.5-14b-instruct-q4_k_m.gguf",
  "llama_port": 8080,
  "telegram_enabled": false,
  "n_gpu_layers": 35,
  "context_size": 8192,
  "n_threads": 8
}
```

### Шаг 4: Создать ярлык

```bash
cd C:\mia
create_shortcut.bat
```

Ярлык появится на рабочем столе: "Mia PM OS"

### Шаг 5: Запустить

Дважды кликните по ярлыку "Mia PM OS" на рабочем столе

## 🎯 Особенности нового GUI:

### Автозапуск LLM
- При запуске Mia автоматически запускает llama.cpp
- LLM работает как фоновый процесс
- При закрытии Mia автоматически останавливает llama.cpp

### Нормальный чат
- Поле ввода снизу
- Кнопки "📤 Send" и "🗑️ Clear"
- Copy-paste работает
- История чата сверху

### Боковая панель
- System Status (LLM, Telegram)
- Quick Actions (Project Ledger, Object Diary, Alerts, Health Score)
- System Logs (автообновление каждые 5 сек)

### Вкладки
- 💬 AI Chat - общение с Mia
- 📱 Telegram - реалтайм чат (заготовка)

## 📦 Рекомендуемые модели:

Для RTX 5060 16GB:

1. **qwen2.5-14b-instruct-q4** (рекомендуется)
   - 14B параметров
   - Отличен для кодинга и рассуждений
   - Ссылка: https://huggingface.co/Qwen/Qwen2.5-14B-Instruct-GGUF

2. **mistral-7b-instruct-q4**
   - 7B параметров
   - Быстрее, но менее точен
   - Ссылка: https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3-GGUF

3. **llama-3.1-8b-instruct-q4**
   - 8B параметров
   - Хорошая баланс между скоростью и качеством
   - Ссылка: https://huggingface.co/lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF

## 🔧 Устранение проблем:

### Ошибка "llama-server.exe not found"
- Скачайте llama.cpp с GitHub
- Распакуйте в `C:\llama.cpp\`
- Обновите путь в `mia_config.json`

### Ошибка "Model not found"
- Скачайте модель с HuggingFace
- Сохраните в `C:\models\`
- Обновите путь в `mia_config.json`

### Ошибка "Port already in use"
- Измените порт в `mia_config.json`
- Или остановите другой процесс на порту 8080

## 📊 Преимущества llama.cpp vs Ollama:

1. **Более легкий** - меньше зависимостей
2. **Быстрее** - оптимизирован для GPU
3. **Больше контроля** - все настройки в конфиге
4. **Проще интеграция** - HTTP API без лишних абстракций
5. **Открытый код** - можно модифицировать

## 🎉 Запуск:

Просто кликните по ярлыку "Mia PM OS" на рабочем столе!
