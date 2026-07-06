@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Mia
echo ============================================
echo   Mia — запуск
echo ============================================
echo.
echo [1/3] Проверяю обновления...
git pull
echo.
echo [2/3] Проверяю зависимости...
python -m pip install -q -r requirements.txt
echo.
echo [3/3] Открываю конфигуратор...
echo.
python run_configurator.py
if errorlevel 1 (
    echo.
    echo Не удалось запустить конфигуратор. Убедитесь, что установлен Python
    echo ^(с поддержкой Tkinter^) и есть доступ в интернет.
    pause
)
