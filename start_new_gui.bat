@echo off
REM Убить все процессы Python и запустить НОВЫЙ GUI

taskkill /F /IM python.exe 2>nul

echo Starting NEW GUI (mia_gui_redesigned.py)...
cd /d C:\mia
python gui\mia_gui_redesigned.py

pause
