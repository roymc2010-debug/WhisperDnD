@echo off
setlocal
chcp 65001 > nul
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo Falta el entorno de desarrollo. Esta prueba todavia no es un EXE instalable.
    pause
    exit /b 1
)
echo WhisperDnD - prueba separada antes del EXE
echo No carga automaticamente tus campanas, claves ni autorizaciones actuales.
echo La ventana debe permanecer abierta mientras pruebas la app.
"%~dp0.venv\Scripts\python.exe" -X utf8 "%~dp0desktop.py" --manual
if errorlevel 1 pause
endlocal
