@echo off
setlocal
cd /d "%~dp0"
title Shin Voice Assistant - Setup

echo ================================================================
echo           Shin Voice Assistant - One-Click Setup
echo ================================================================
echo.

if exist "setup.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
) else (
    echo [ERROR] setup.ps1 not found!
)

echo.
pause
