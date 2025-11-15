Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")

' VBS dosyasının bulunduğu klasörü al
scriptFolder = fso.GetParentFolderName(WScript.ScriptFullName)

' Çalışma dizinini VBS klasörü olarak ayarla
WshShell.CurrentDirectory = scriptFolder

' run.bat dosyasını gizli şekilde çalıştır
batPath = scriptFolder & "\run.bat"
WshShell.Run Chr(34) & batPath & Chr(34), 0, False

Set WshShell = Nothing
Set fso = Nothing
