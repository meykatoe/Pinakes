@echo off
title Pinakes console
cd /d "%~dp0backend"
set "PATH=%~dp0ffmpeg\bin;%PATH%"
"%~dp0python\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
