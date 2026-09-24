@echo off
title WhisperDnD - Mobile Remote Access & HTTPS Tunnel Launcher
cd /d "%~dp0\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tunnel.ps1"
pause
