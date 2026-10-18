@echo off
title WhisperDnD Server
cd /d "%~dp0"
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

