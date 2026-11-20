@echo off
setlocal
cd /d "%~dp0"
title Shin Voice Assistant - Setup

echo ================================================================
echo           Shin Voice Assistant - One-Click Setup
echo ================================================================
echo.

if exist "Shin\setup.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Shin\setup.ps1"
) else if exist "setup.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
) else (
    echo [ERROR] setup.ps1 not found in current directory or Shin\ folder!
)

echo.
pause
