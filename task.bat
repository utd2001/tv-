@echo off
setlocal

:: VBS dosyasının bulunduğu klasörü al
set "scriptdir=%~dp0"
set "vbsfile=%scriptdir%run.vbs"

:: Görev adı
set "taskname=GithubTV"

:: Mevcut görevi sil (varsa)
schtasks /Delete /TN "%taskname%" /F >nul 2>&1

:: Yeni görev oluştur (her 2 saatte bir çalışacak)
schtasks /Create ^
    /SC HOURLY ^
    /MO 2 ^
    /TN "%taskname%" ^
    /TR "wscript.exe \"%vbsfile%\"" ^
    /F

echo [✓] Görev eklendi: %taskname%
pause
