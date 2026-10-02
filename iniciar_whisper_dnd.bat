@echo off
title WhisperDnD Launcher
chcp 65001 > nul
cd /d "%~dp0"

:: 1. Si el servidor no esta corriendo en el puerto 8080, levantarlo en segundo plano
netstat -aon | findstr :8080 | findstr LISTENING > nul
if errorlevel 1 (
    start /min "" "%~dp0.venv\Scripts\python.exe" "%~dp0main.py"
    timeout /t 2 /nobreak > nul
)

:: 2. Abrir como ventana de aplicacion
if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" (
    start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --app=http://localhost:8080
) else if exist "C:\Program Files\Microsoft\Edge\Application\msedge.exe" (
    start "" "C:\Program Files\Microsoft\Edge\Application\msedge.exe" --app=http://localhost:8080
) else if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --app=http://localhost:8080
) else (
    start "" http://localhost:8080
)
exit
