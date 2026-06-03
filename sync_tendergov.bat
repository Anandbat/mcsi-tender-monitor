@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ================================
echo  tender.gov.mn sync starting...
echo ================================
python -X utf8 sync_tendergov.py
echo.
pause
