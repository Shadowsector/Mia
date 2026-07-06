@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Mia - Установка зависимостей
echo ============================================
echo   Установка зависимостей Mia
echo ============================================
echo.
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
if errorlevel 1 (
    echo Во время установки возникли ошибки. Проверьте вывод выше.
) else (
    echo Готово! Зависимости установлены.
    echo.
    echo Дальше:
    echo   1^) Скопируйте .env.example в .env и впишите BOT_TOKEN ^(если ещё не сделали^).
    echo   2^) Установите модели Ollama:
    echo        ollama pull qwen2.5:14b-instruct
    echo        ollama pull bge-m3
    echo   3^) Запустите start_bot.bat
)
echo.
pause
