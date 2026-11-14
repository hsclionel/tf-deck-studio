@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe service.py stop --port 8081
pause
