@echo off
setlocal
cd /d "%~dp0"
title WhisperDnD - Rediseño (8081)
if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" "%~dp0scripts\preview_design.py" %*
) else if exist "%USERPROFILE%\WhisperDnD-Lab\.venv\Scripts\python.exe" (
  "%USERPROFILE%\WhisperDnD-Lab\.venv\Scripts\python.exe" "%~dp0scripts\preview_design.py" %*
) else (
  echo Falta Python con las dependencias. Crea .venv e instala requirements.txt.
)
pause
