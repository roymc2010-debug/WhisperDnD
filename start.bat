@echo off
title WhisperDnD Server
cd /d "%~dp0"
if "%1"=="--show-console" goto run_foreground
if "%1"=="--console" goto run_foreground
if defined SHOW_CONSOLE goto run_foreground

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" main.py %*
    exit /b 0
)

:run_foreground
echo ========================================================
echo   Iniciando WhisperDnD Server en http://localhost:8080
echo ========================================================
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py %*
) else (
    python main.py %*
)
if errorlevel 1 (
    echo.
    echo [!] El servidor finalizo con un error.
    pause
)


