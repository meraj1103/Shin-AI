@echo off
setlocal
cd /d "%~dp0"
title Create Shin Desktop Shortcut

if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else if exist "Shin\.venv\Scripts\python.exe" (
    set "PY=Shin\.venv\Scripts\python.exe"
) else (
    set "PY=python"
)

if exist "Shin\create_desktop_shortcut.py" (
    "%PY%" Shin\create_desktop_shortcut.py
) else if exist "create_desktop_shortcut.py" (
    "%PY%" create_desktop_shortcut.py
) else (
    echo [ERROR] create_desktop_shortcut.py not found!
)

echo.
pause
