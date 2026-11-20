@echo off
setlocal
cd /d "%~dp0"
title Start Shin Voice Assistant

if exist "Shin\start_shin.bat" (
    cd /d "%~dp0Shin"
    call start_shin.bat
) else if exist "start_shin.bat" (
    call start_shin.bat
) else (
    echo [ERROR] start_shin.bat not found in current directory or Shin\ folder!
    pause
)
