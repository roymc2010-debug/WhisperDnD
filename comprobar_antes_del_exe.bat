@echo off
setlocal
chcp 65001 > nul
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo Falta el entorno de desarrollo.
    pause
    exit /b 1
)
"%~dp0.venv\Scripts\python.exe" -X utf8 "%~dp0desktop.py" --manual --check
pause
endlocal
