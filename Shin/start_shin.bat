@echo off
cd /d "%~dp0"
echo Starting Shin Voice Assistant in the background...
wscript.exe "%~dp0start_shin.vbs"
echo Done! Shin is now running in the background.
echo You can close this terminal/IDE, Shin will stay online.
echo.
echo To stop Shin: Right-click the cyan circle icon in your System Tray and click "Quit Shin".
ping 127.0.0.1 -n 6 >nul
