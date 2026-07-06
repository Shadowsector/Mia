@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Mia - Обновление
echo ============================================
echo   Обновление Mia из GitHub
echo ============================================
echo.
git pull
if errorlevel 1 (
    echo.
    echo Не удалось обновиться. Убедитесь, что проект скачан через git clone
    echo и установлен Git.
) else (
    echo.
    echo Обновление завершено. При необходимости выполните install.bat,
    echo если менялись зависимости, и перезапустите бота.
)
echo.
pause
