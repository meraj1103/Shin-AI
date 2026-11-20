# rebuild_venv.ps1 — Cleanly rebuild .venv using Python 3.12
$ErrorActionPreference = "Continue"

Write-Host "`n=== Rebuilding Shin Virtual Environment with Python 3.12 ===" -ForegroundColor Cyan

# 1. Terminate orphaned python processes locking .venv
Write-Host "`n[1/5] Stopping any running Shin / Python processes..." -ForegroundColor Yellow
Get-Process python*, pythonw* -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# 2. Navigate to project root
$rootDir = Resolve-Path "$PSScriptRoot\.."
Set-Location $rootDir

# 3. Remove old Python 3.14 virtual environment
Write-Host "[2/5] Removing old Python 3.14 virtual environment..." -ForegroundColor Yellow
if (Test-Path "$rootDir\.venv") {
    Remove-Item -Recurse -Force "$rootDir\.venv" -ErrorAction SilentlyContinue
}
if (Test-Path "$PSScriptRoot\.venv") {
    Remove-Item -Recurse -Force "$PSScriptRoot\.venv" -ErrorAction SilentlyContinue
}

# 4. Create clean Python 3.12 venv
Write-Host "[3/5] Creating clean virtual environment with Python 3.12..." -ForegroundColor Yellow
$py = $null
try {
    $ver = & py -3.12 --version 2>&1
    if ($ver -match "Python 3\.12") {
        $py = "py"
        $pyArgs = @("-3.12")
    }
} catch {}

if (-not $py) {
    $candidate = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
    if (Test-Path $candidate) {
        $py = $candidate
        $pyArgs = @()
    }
}

if (-not $py) {
    Write-Host "[ERROR] Could not find Python 3.12." -ForegroundColor Red
    exit 1
}

& $py $pyArgs -m venv "$rootDir\.venv"

if (-not (Test-Path "$rootDir\.venv\Scripts\python.exe")) {
    Write-Host "[ERROR] Failed to create virtual environment." -ForegroundColor Red
    exit 1
}

# 5. Upgrade pip and install PyAudio and requirements
Write-Host "[4/5] Upgrading pip and installing PyAudio & webrtcvad-wheels pre-compiled wheels..." -ForegroundColor Yellow
& "$rootDir\.venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
& "$rootDir\.venv\Scripts\pip.exe" install PyAudio webrtcvad-wheels --quiet

Write-Host "[5/5] Installing dependencies from Shin\requirements.txt..." -ForegroundColor Yellow
& "$rootDir\.venv\Scripts\pip.exe" install -r "$PSScriptRoot\requirements.txt"

Write-Host "`n=== Setup complete! Virtual environment is now running Python 3.12 ===" -ForegroundColor Green
Write-Host "To run Shin:" -ForegroundColor Cyan
Write-Host "  & `"$rootDir\.venv\Scripts\python.exe`" `"$PSScriptRoot\assistant.py`"`n"
