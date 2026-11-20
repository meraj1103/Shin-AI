@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Shin Voice Assistant

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
) else if exist "Shin\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0Shin\.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo [Shin] Using Python: !PYTHON_EXE!
"%PYTHON_EXE%" Shin\assistant.py %*

if errorlevel 1 (
    echo.
    echo [Shin] Assistant exited with code %errorlevel%.
    pause
)
