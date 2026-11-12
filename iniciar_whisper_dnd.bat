@echo off
setlocal
chcp 65001 > nul
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
    echo No se encontro Python de WhisperDnD en .venv. Revisa la instalacion.
    pause
    exit /b 1
)
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0scripts\launch_desktop.py"
exit /b
