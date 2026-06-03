@echo off
title MCSI Tender Monitor
color 0B

echo.
echo  ============================================
echo   MCSI Tender Monitor
echo  ============================================
echo.

:: Use PowerShell to find python.exe anywhere on disk
echo  [*] Python haij bna...
for /f "delims=" %%i in ('powershell -NoProfile -Command "Get-ChildItem -Path C:\Users,$env:LOCALAPPDATA,'C:\Program Files','C:\Program Files (x86)','C:\' -Filter python.exe -Recurse -ErrorAction SilentlyContinue | Where-Object {$_.FullName -notmatch 'WindowsApps'} | Select-Object -First 1 -ExpandProperty FullName"') do set PYTHON=%%i

if not defined PYTHON (
    echo  [ERROR] Python oldogdsonggui!
    echo.
    echo  PowerShell-d doordahi commandyg ajillaulaad hariu ilgeene uu:
    echo  Get-ChildItem C:\ -Filter python.exe -Recurse -ErrorAction SilentlyContinue ^| Select FullName
    echo.
    pause
    exit /b 1
)

echo  [OK] Python: %PYTHON%
echo.
echo  [*] Dependencies suulgaj bna...
"%PYTHON%" -m pip install -r requirements.txt -q
echo  [OK] Done.
echo.
echo  ============================================
echo   Server: http://localhost:8000
echo   Chrome-d mcsi-tender-monitor.html neene
echo   En tsongkhyg KHAAJ BOLOHGUI!
echo  ============================================
echo.

"%PYTHON%" run.py

pause
