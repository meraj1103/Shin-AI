# setup.ps1 — One-shot setup script for Shin Voice Assistant
# Run from the Shin\ directory with:  .\setup.ps1

$ErrorActionPreference = "Stop"

Write-Host "`n===  Shin Voice Assistant Setup  ===" -ForegroundColor Cyan

# 1. Locate compatible Python 3.10 - 3.12
# (Python >= 3.14 lacks pre-compiled wheels for PyAudio, PyTorch, Vosk, Whisper, MediaPipe)
$py = $null
$pyArgs = @()

# First check if Python launcher has 3.12, 3.11, or 3.10
foreach ($v in @("-3.12", "-3.11", "-3.10")) {
    try {
        $ver = & py $v --version 2>&1
        if ($ver -match "Python 3\.(1[0-2])\.") {
            $py = "py"
            $pyArgs = @($v)
            Write-Host "  Found via py launcher: $ver ($py $v)" -ForegroundColor Green
            break
        }
    } catch {}
}

if (-not $py) {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe",
        "C:\Python310\python.exe",
        "python",
        "python3"
    )

    foreach ($c in $candidates) {
        try {
            $ver = & $c --version 2>&1
            # Ensure Python is 3.10, 3.11, or 3.12 (not 3.14+)
            if ($ver -match "Python 3\.(1[0-2])\.") {
                $py = $c
                $pyArgs = @()
                Write-Host "  Found compatible Python: $ver ($c)" -ForegroundColor Green
                break
            }
        } catch {}
    }
}

if (-not $py) {
    Write-Host "`n[ERROR] Compatible Python (3.10 - 3.12) not found." -ForegroundColor Red
    Write-Host "Python 3.14+ is not yet supported by PyAudio, PyTorch, and Whisper wheels." -ForegroundColor Yellow
    Write-Host "Please install Python 3.12 from https://www.python.org/downloads/release/python-31210/ and re-run."
    exit 1
}

# 2. Locate or create virtual environment
$venvDir = if (Test-Path ".venv") { ".venv" } elseif (Test-Path "..\.venv") { "..\.venv" } else { ".venv" }

if (-not (Test-Path "$venvDir\pyvenv.cfg")) {
    Write-Host "`n[1/4] Creating virtual environment ($venvDir)..." -ForegroundColor Yellow
    if (Test-Path $venvDir) {
        Remove-Item -Recurse -Force $venvDir -ErrorAction SilentlyContinue
    }
    & $py $pyArgs -m venv $venvDir
} else {
    Write-Host "`n[1/4] Virtual environment already exists ($venvDir)." -ForegroundColor Gray
}

# 3. Activate and upgrade pip, install pre-compiled binary wheels
Write-Host "[2/4] Upgrading pip and installing binary wheels (webrtcvad, PyAudio)..." -ForegroundColor Yellow
& "$venvDir\Scripts\python.exe" -m pip install --upgrade pip --quiet
& "$venvDir\Scripts\pip.exe" install webrtcvad-wheels PyAudio --quiet

# Ensure pip resolver recognizes webrtcvad as satisfied without needing C++ build tools
$spDir = & "$venvDir\Scripts\python.exe" -c "import site; print(site.getsitepackages()[0])"
$vadMetaDir = "$spDir\webrtcvad-2.0.14.dist-info"
if (-not (Test-Path $vadMetaDir)) {
    New-Item -ItemType Directory -Force -Path $vadMetaDir | Out-Null
    @"
Metadata-Version: 2.4
Name: webrtcvad
Version: 2.0.14
Summary: Python interface to the Google WebRTC Voice Activity Detector (VAD)
Author: John Wiseman
License: MIT
"@ | Set-Content "$vadMetaDir\METADATA"
    "pip" | Set-Content "$vadMetaDir\INSTALLER"
}

# 4. Install requirements
Write-Host "[3/4] Installing dependencies (this may take a few minutes)..." -ForegroundColor Yellow
$reqPath = if (Test-Path "requirements.txt") { "requirements.txt" } else { "Shin\requirements.txt" }
& "$venvDir\Scripts\pip.exe" install -r $reqPath

# PyAudio check (safely without crashing on NativeCommandError)
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
$pyaudio_ok = & "$venvDir\Scripts\python.exe" -c "import pyaudio; print('ok')"
$ErrorActionPreference = $prevEAP
if ($pyaudio_ok -notmatch "ok") {
    Write-Host "  Retrying install for PyAudio..." -ForegroundColor Yellow
    & "$venvDir\Scripts\pip.exe" install PyAudio
}

# 5. Copy .env if missing
if (-not (Test-Path ".env")) {
    Write-Host "[4/4] Creating .env from template..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "  Edit .env to add optional API keys." -ForegroundColor Gray
} else {
    Write-Host "[4/4] .env already exists." -ForegroundColor Gray
}

# 6. Check Ollama and pull fallback models
if (Get-Command "ollama" -ErrorAction SilentlyContinue) {
    Write-Host "`n[Ollama] Found local Ollama server." -ForegroundColor Green
    Write-Host "  Pulling fallback models (llama3, translategemma)..." -ForegroundColor Yellow
    try {
        & ollama pull llama3
        & ollama pull translategemma
    } catch {
        Write-Host "  Could not pull models. Make sure Ollama server is running." -ForegroundColor Yellow
    }
} else {
    Write-Host "`n[Ollama] Ollama not found. Install it from https://ollama.com to enable offline NLP." -ForegroundColor Gray
}

Write-Host "`n=== Setup complete! ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Activate environment:  .venv\Scripts\Activate.ps1"
Write-Host "  Run the assistant:     python assistant.py          (waits for wake word)"
Write-Host "  Run without wake word: python assistant.py --no-wake (listens continuously)"
Write-Host "  Run tests:             python -m pytest tests/ -v"
Write-Host ""
