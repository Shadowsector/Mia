@echo off
REM Запуск интеграционных тестов Mia PM OS
echo ============================================
echo Интеграционные тесты
echo ============================================
echo.
echo Проверка:
echo   - Ollama соединение
echo   - Генерация текста и JSON
echo   - ChromaDB (RAG)
echo   - Diary Manager
echo   - Temporal Logic
echo.
pause

cd /d C:\mia
python scripts\test_integration.py

echo.
echo ============================================
echo Тесты завершены!
echo ============================================
echo.
pause
