@echo off
cd /d "%~dp0"
echo Stopping Shin Voice Assistant...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name = 'pythonw.exe' or Name = 'python.exe'\" | Where-Object { $_.CommandLine -like '*assistant.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; echo 'Stopped Shin process with PID ' $_.ProcessId }"
echo.
echo Cleaning up any orphaned 3D Orb overlay windows...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name = 'electron.exe'\" | Where-Object { $_.CommandLine -like '*orb-electron*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; echo 'Stopped Orb process with PID ' $_.ProcessId }"
echo.
echo Cleaning up any running Cloudflare tunnels...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name = 'cloudflared.exe'\" | Where-Object { $_.CommandLine -like '*5055*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; echo 'Stopped Cloudflare tunnel with PID ' $_.ProcessId }"
taskkill /F /IM MateEngineX.exe >nul 2>&1
echo.
echo Shin has been stopped.
ping 127.0.0.1 -n 6 >nul
