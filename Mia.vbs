' Тихий запуск Mia — без чёрного окна консоли.
' Запускает Mia.bat скрыто (обновление + зависимости + конфигуратор).
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = scriptDir
' 0 = скрытое окно, False = не ждать завершения
sh.Run "cmd /c """ & scriptDir & "\Mia.bat""", 0, False
