Dim fso, scriptDir, WshShell, command

Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set fso = Nothing

Set WshShell = CreateObject("WScript.Shell")

WshShell.CurrentDirectory = scriptDir

command = "cmd.exe /c start /B pythonw.exe server.pyw & pythonw.exe github.pyw"
WshShell.Run command, 0, true

Set WshShell = Nothing