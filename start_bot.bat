@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Mia - Bot
echo ============================================
echo   Запуск бота Mia
echo ============================================
echo.
echo Убедитесь, что запущен Ollama (ollama serve).
echo Для остановки бота закройте это окно или нажмите Ctrl+C.
echo.
python run.py
echo.
echo Бот остановлен.
pause
