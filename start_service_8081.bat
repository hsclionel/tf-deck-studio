@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe service.py start --port 8081
pause
