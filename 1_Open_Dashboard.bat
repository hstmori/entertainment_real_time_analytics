@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0back\scripts\demo\open-dashboard.ps1"
echo.
pause
