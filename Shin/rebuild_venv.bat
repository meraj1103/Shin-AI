@echo off
cd /d "%~dp0\.."
echo =====================================================
echo   Rebuilding Shin Virtual Environment with Python 3.12
echo =====================================================
echo.

echo [1/5] Stopping any running Shin / Python processes...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM pythonw.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/5] Removing old Python 3.14 virtual environment...
if exist ".venv" (
    rmdir /s /q ".venv"
)
if exist "Shin\.venv" (
    rmdir /s /q "Shin\.venv"
)

echo [3/5] Creating clean virtual environment with Python 3.12...
py -3.12 -m venv .venv
if not exist ".venv\Scripts\python.exe" (
    echo   Fallback: Trying direct Python 3.12 path...
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m venv .venv
)

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Failed to create virtual environment with Python 3.12.
    echo Please ensure Python 3.12 is installed and available.
    pause
    exit /b 1
)

echo [4/5] Upgrading pip and installing PyAudio & webrtcvad wheels...
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
.venv\Scripts\pip.exe install PyAudio webrtcvad-wheels --quiet

echo [5/5] Installing dependencies from Shin\requirements.txt...
.venv\Scripts\pip.exe install -r Shin\requirements.txt

echo.
echo =====================================================
echo   Success! Environment is ready with Python 3.12.
echo   To launch Shin:
echo     .venv\Scripts\python.exe Shin\assistant.py
echo =====================================================
pause
