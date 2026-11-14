@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0back\scripts\demo\run-pipeline-demo.ps1"
echo.
pause
