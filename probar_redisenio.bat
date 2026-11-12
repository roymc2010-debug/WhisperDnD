@echo off
setlocal
cd /d "%~dp0"
title WhisperDnD - Vista previa del rediseño

set "ARGS=%*"
if "%ARGS%"=="" set "ARGS=--with-drive"
if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" "%~dp0scripts\preview_design.py" %ARGS%
) else if exist "%USERPROFILE%\WhisperDnD-Lab\.venv\Scripts\python.exe" (
  "%USERPROFILE%\WhisperDnD-Lab\.venv\Scripts\python.exe" "%~dp0scripts\preview_design.py" %ARGS%
) else (
  echo Falta Python con las dependencias. Crea .venv e instala requirements.txt.
)
pause
