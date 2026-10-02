@echo off
title Detener WhisperDnD
chcp 65001 > nul
echo Deteniendo servidor WhisperDnD...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8080') do taskkill /f /pid %%a > nul 2>&1
echo Servidor detenido correctamente.
timeout /t 2 > nul
