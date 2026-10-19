@echo off
REM Создание ярлыка на рабочем столе для Mia PM OS

set TARGET=C:\mia\gui\mia_gui_redesigned.py
set SCRIPT=C:\Users\MSI\AppData\Local\Programs\Python\Python312\python.exe
set SHORTCUT=%USERPROFILE%\Desktop\Mia PM OS.lnk

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '%SCRIPT%'; $s.Arguments = '%TARGET%'; $s.WorkingDirectory = 'C:\mia'; $s.Description = 'Mia PM OS - Construction Project Management'; $s.Save()"

echo Ярлык создан на рабочем столе: Mia PM OS.lnk
pause
