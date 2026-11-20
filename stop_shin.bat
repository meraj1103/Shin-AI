@echo off
setlocal
cd /d "%~dp0"
title Stop Shin Voice Assistant

if exist "Shin\stop_shin.bat" (
    cd /d "%~dp0Shin"
    call stop_shin.bat
) else (
    echo Stopping Shin Voice Assistant...
    powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name = 'pythonw.exe' or Name = 'python.exe'\" | Where-Object { $_.CommandLine -like '*assistant.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; echo 'Stopped Shin process with PID ' $_.ProcessId }"
    taskkill /F /IM MateEngineX.exe >nul 2>&1
    echo Shin has been stopped.
    ping 127.0.0.1 -n 4 >nul
)
