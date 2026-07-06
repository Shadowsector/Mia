@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Mia - Configurator
echo ============================================
echo   Запуск конфигуратора Mia
echo ============================================
echo.
python run_configurator.py
if errorlevel 1 (
    echo.
    echo Не удалось запустить конфигуратор. Проверьте, что установлен Python
    echo с поддержкой Tkinter и выполнена установка зависимостей ^(install.bat^).
    pause
)
