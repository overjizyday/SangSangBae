@echo off
set "PROJECT_ROOT=%~dp0.."
set "PYTHON=C:\Users\endy0\AppData\Local\Programs\Python\Python311\python.exe"
set "LOG_DIR=%PROJECT_ROOT%\logs"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

cd /d "%PROJECT_ROOT%"
set PYTHONUNBUFFERED=1

"%PYTHON%" -m uvicorn main:app --host 0.0.0.0 --port 8080 >> "%LOG_DIR%\private_drive_app.log" 2>&1
