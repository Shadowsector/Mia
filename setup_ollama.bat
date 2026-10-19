@echo off
REM Настройка Ollama для Mia PM OS
echo ============================================
echo Настройка Ollama - Загрузка моделей
echo ============================================
echo.
echo Будут загружены модели по RFC v1.9:
echo   - mistral:7b-instruct-v0.3 (классификация)
echo   - qwen2.5:14b-instruct-q4_K_M (анализ связей)
echo   - nomic-embed-text (эмбеддинги)
echo.
pause

cd /d C:\mia
python scripts\setup_ollama.py

echo.
echo ============================================
echo Настройка завершена!
echo ============================================
echo.
pause
