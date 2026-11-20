# 🤖 Shin — Personal AI Voice Assistant

> A fully offline-capable, Windows-native voice assistant built by **MJ** (Meharaj SohabatAli Ansari).  
> Supports Hindi & English, AI chat (OpenAI / Gemini / Ollama), deep Windows automation, and a **living personality** that adapts to your mood and context.

---

## 📑 Table of Contents

1. [Overview](#overview)
2. [System Requirements](#system-requirements)
3. [Project File Structure](#project-file-structure)
4. [Installation Guide](#installation-guide)
5. [Configuration (.env)](#configuration-env)
6. [Offline Setup (Vosk Models)](#offline-setup-vosk-models)
7. [How to Run Shin](#how-to-run-shin)
8. [All Features & Commands](#all-features--commands)
9. [Proactive Senses (Alerts)](#proactive-senses-alerts)
10. [AI Backends](#ai-backends)
11. [Voice & Speech Settings](#voice--speech-settings)
12. [Security Guardrails](#security-guardrails)
13. [Developer Guide](#developer-guide)

---

## Overview

Shin is a personal AI voice assistant designed to run natively on Windows. It uses a three-tier NLP system — fast rule-based parsing → cloud AI fallback → local Ollama LLM — ensuring it works whether you're online or completely offline.

**Key highlights:**
- 🎙️ Wake-word detection: **"Hey Shin"**
- 🎭 **Living Personality** — varied Hinglish responses, mood engine, thinking out loud, and a warm, caring best-friend tone
- 🧠 **Situational AI Fallback** — OpenAI/Gemini gets live context (current time, day, weekend status, Shin's current mood, your active application, and recent command history)
- 🤫 **Proactive chatter** — checks in randomly every 15–25 min without being asked
- 🌐 Online TTS: Microsoft Edge Neural Voices (intelligent routing: English voice for English and Romanized Hinglish, Hindi voice for Devanagari script to avoid mispronunciation)
- 📴 Offline fallback: Vosk ASR + pyttsx3 TTS (no internet needed)
- 🧠 Understands Hindi, English, and Hinglish
- 🪟 Transparent 3D animated orb overlay (Electron/WebGL)
- 🔒 Voice biometrics (speaker verification via Resemblyzer)
- 🛡️ System security guardrails (blocks dangerous commands)
- 💤 "I'm going to sleep" → Good night + automatic shutdown

---

## System Requirements

| Component | Minimum |
|---|---|
| OS | Windows 10 / 11 (64-bit) |
| Python | 3.10 – 3.12 |
| RAM | 4 GB (8 GB+ recommended) |
| Microphone | Any USB or 3.5mm mic |
| Internet | Optional (offline mode available) |
| GPU | Optional (only for Whisper ASR) |

> **MJ's Setup**: AMD Ryzen 5 5600H · 16 GB RAM · NVIDIA RTX 3050

---

## Project File Structure

```
Shin/
├── assistant.py            ← Main entry point — ASR loop, TTS worker, personality init
├── .env                    ← Your personal config & API keys (never commit this)
├── .env.example            ← Template for .env
├── requirements.txt        ← All Python dependencies
├── setup.ps1               ← One-click Windows setup script
├── conftest.py             ← Pytest configuration
│
├── core/                   ← All logic modules
│   ├── personality.py      ← ★ NEW — Shin's living personality engine (mood, phrases, Hinglish)
│   ├── alerts.py           ← Proactive background alerts (battery, water, bedtime, etc.)
│   ├── api_manager.py      ← API key validation & management
│   ├── calendar_ai.py      ← Google Calendar integration
│   ├── clipboard_ai.py     ← AI clipboard actions (translate, rewrite, summarize)
│   ├── clipboard_history.py← Clipboard change monitor
│   ├── command_log.py      ← Logs all commands and responses
│   ├── commands.py         ← All Windows automation handlers (open apps, control volume, etc.)
│   ├── gmail_ai.py         ← Gmail read integration
│   ├── gestures.py         ← Real-time hand gesture recognition (MediaPipe + OpenCV)
│   ├── macros.py           ← Custom macro (shortcut) recording and playback
│   ├── memory.py           ← Persistent memory (save facts, recall them later)
│   ├── news.py             ← World News API integration
│   ├── nlp.py              ← Natural Language Processing — intent parser + mood detection
│   ├── orb_window.py       ← Floating orb overlay launcher (Electron)
│   ├── smart_home.py       ← Tuya smart home device control
│   ├── spotify_ai.py       ← Spotify playback control
│   ├── todo.py             ← To-do list management
│   ├── token_tracker.py    ← Tracks OpenAI/Gemini API token usage
│   ├── ui_server.py        ← Local HTTP + WebSocket server for the Orb UI
│   ├── vision.py           ← Screen reading and OCR (pytesseract)
│   ├── voice_auth.py       ← Speaker identity verification (Resemblyzer)
│   └── weather.py          ← OpenWeatherMap integration
│
├── ui/
│   └── orb.html            ← 3D animated orb overlay (WebGL)
│
├── core/orb-electron/      ← Electron shell for the floating orb window
│
├── languages/              ← Vosk offline speech models (you download these)
│   ├── vosk-model-en-us-0.22/
│   ├── vosk-model-en-in-0.5/
│   └── vosk-model-hi-0.22/
│
├── data/                   ← Runtime data (auto-created)
│   ├── voice_profile.npy   ← Your enrolled voice biometric
│   ├── memory.json         ← Remembered facts
│   └── missed_intents.log  ← Commands Shin couldn't understand (for improvement)
│
├── tests/
│   ├── test_nlp.py         ← 145 unit tests for intent parsing
│   └── test_voice_bypass.py← Voice auth bypass tests
│
└── mate engin/             ← Optional: 3D avatar/mascot (MateEngineX)
```

---

## Installation Guide

### Step 1 — Download the Project

```bash
git clone https://github.com/YourUsername/Shin.git
cd Shin
```

Or just download and extract the ZIP file.

---

### Step 2 — Run the Setup Script (Recommended)

Open **PowerShell** in the `Shin/` folder and run:

```powershell
.\setup.ps1
```

This script automatically:
1. Finds your Python 3.10+ installation
2. Creates a `.venv` virtual environment
3. Installs all dependencies from `requirements.txt`
4. Copies `.env.example` → `.env` if it doesn't exist
5. Pulls Ollama models (if Ollama is installed)

---

### Step 3 — Manual Installation (Alternative)

If you prefer to do it manually:

```powershell
# Create virtual environment
python -m venv .venv

# Activate it
.\.venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip

# Install all dependencies
pip install -r requirements.txt
```

> **Note on PyAudio**: If `pip install` fails for PyAudio, install it with `pipwin`:
> ```powershell
> pip install pipwin
> pipwin install pyaudio
> ```

---

### Step 4 — Configure Your .env

```powershell
copy .env.example .env
```

Then open `.env` and fill in your settings (see [Configuration](#configuration-env) below).

---

### Step 5 — Optional: Install Ollama (for offline AI)

Download from https://ollama.com, install it, then pull models:

```bash
ollama pull llama3
ollama pull translategemma
```

---

## Configuration (.env)

Open the `.env` file in any text editor and configure the following:

```env
# ── AI Backends (optional — leave blank to use local Ollama or rule-based NLP)
OPENAI_API_KEY=sk-...            # Get from https://platform.openai.com
GEMINI_API_KEY=AIza...           # Get from https://aistudio.google.com
OLLAMA_MODEL=llama3              # Local AI (no key needed, just Ollama installed)

# ── Speech Recognition
ASR_BACKEND=google               # "google" (online) or "vosk" (offline)
ASR_LANGUAGE=auto                # "auto" to auto-detect, or "hi-IN" / "en-US"

# ── Text-to-Speech
TTS_BACKEND=edge                 # "edge" (Microsoft neural, online) or "pyttsx3" (offline)
EDGE_TTS_VOICE=hi-IN-SwaraNeural     # Hindi female voice
EDGE_TTS_VOICE_EN=en-US-EmmaNeural  # English female voice

# ── Wake Word
WAKE_WORD=hey shin               # Say this phrase to activate Shin

# ── Weather
OPENWEATHER_API_KEY=your_key     # Get free key from https://openweathermap.org/api
WEATHER_CITY=Mumbai              # Your city for weather lookups

# ── Spotify
SPOTIPY_CLIENT_ID=...            # From https://developer.spotify.com
SPOTIPY_CLIENT_SECRET=...
SPOTIPY_REDIRECT_URI=http://localhost:8888/callback

# ── Smart Home (Tuya devices)
TUYA_DEVICE_ID=...
TUYA_IP=...
TUYA_LOCAL_KEY=...

# ── Voice Biometrics
VOICE_AUTH_ENABLED=true          # Shin only listens to your voice
VOICE_AUTH_THRESHOLD=0.75        # Similarity score (0.0–1.0)

# ── Offline Vosk Model Path (only if ASR_BACKEND=vosk)
VOSK_MODEL_PATH=./languages/vosk-model-en-us-0.22

# ── Noise Reduction
USE_NOISE_REDUCTION=true         # Uses noisereduce library for cleaner audio

# ── Performance
OLLAMA_KEEP_ALIVE=1m             # How long to keep LLM model in RAM
DISABLE_MASCOT=false             # Set true for lightweight headless mode
```

### Where to get free API keys:
| Service | URL |
|---|---|
| OpenWeather | https://openweathermap.org/api |
| World News | https://worldnewsapi.com |
| OpenAI | https://platform.openai.com |
| Google Gemini | https://aistudio.google.com |
| Spotify | https://developer.spotify.com |

---

## Offline Setup (Vosk Models)

Shin can work **completely offline** for speech recognition using Vosk models.  
Download models from: **https://alphacephei.com/vosk/models**

Recommended models to download and extract into `Shin/languages/`:

| Model | Language | Size | Folder Name |
|---|---|---|---|
| vosk-model-en-us-0.22 | English (US) | ~1.8 GB | `languages/vosk-model-en-us-0.22/` |
| vosk-model-en-in-0.5 | English (India) | ~1.0 GB | `languages/vosk-model-en-in-0.5/` |
| vosk-model-hi-0.22 | Hindi | ~500 MB | `languages/vosk-model-hi-0.22/` |
| vosk-model-small-en-us-0.15 | English (lightweight) | ~45 MB | `languages/vosk-model-small-en-us/` |

> **Important**: After extracting a zip file, if you see a double-nested folder like  
> `languages/vosk-model-en-us-0.22/vosk-model-en-us-0.22/am/...`  
> Shin will automatically detect this and load it correctly. No manual fix needed.

Then set in `.env`:
```env
ASR_BACKEND=vosk
VOSK_MODEL_PATH=./languages/vosk-model-en-us-0.22
```

---

## How to Run Shin

### Running in the Foreground (with Console Logs)

```powershell
# Activate virtual environment first
.\.venv\Scripts\Activate.ps1

# Run respecting WAKE_WORD_ENABLED in .env (default)
python assistant.py

# Run with wake-word detection forced
python assistant.py --wake

# Run with continuous listening (no wake word) forced
python assistant.py --no-wake

# Run with verbose debug logging
python assistant.py --debug
```

### Running in the Background (Survives IDE/Terminal Close)

If you run Shin in the integrated terminal of an IDE (like Antigravity or VS Code), closing the IDE will shut down the terminal and turn Shin offline. To run Shin detached in the background so it survives closing your editor/terminal:

- Double-click `start_shin.bat` in the project root folder.
- Or run it from PowerShell: `.\start_shin.bat`

This launches Shin silently using `pythonw.exe`. You can manage it using the cyan circle icon in the Windows System Tray.

To stop the background process:
- Right-click the **System Tray icon** → **"Quit Shin"** (preferred as it performs full cleanup).
- Or run `.\stop_shin.bat`.

### Adding Shin to Windows Startup (Auto-Start)

Once Shin is running, right-click the **tray icon** → **"Run on Startup"**. Shin will start automatically on boot.

Alternatively, run `python create_desktop_shortcut.py` to create a desktop shortcut.

---

## All Features & Commands

### 🖥️ App Control

| You say | What happens |
|---|---|
| "Open Chrome" | Launches Chrome |
| "Open VS Code" | Launches Visual Studio Code |
| "Open calculator" | Launches Windows Calculator |
| "Close Chrome" | Closes Chrome |
| "Close active window" | Closes the currently focused window |
| "Minimize all" | Minimizes all windows |
| "Snap left / right" | Snaps window to left/right half |
| "Maximize this window" | Maximizes current window |

---

### 🔊 Volume & Media

| You say | What happens |
|---|---|
| "Volume up / down" | Adjusts system volume by 10% |
| "Set volume to 60" | Sets exact volume level |
| "Mute / Unmute" | Mutes or unmutes system audio |
| "Lower Chrome's volume" | Reduces volume for only Chrome |
| "Play / Pause" | Play/pause current media |
| "Next track / Previous track" | Skip songs |

---

### 🌤️ Weather & Time

| You say | What happens |
|---|---|
| "What's the weather?" | Current weather for your configured city |
| "Will it rain today?" | 12-hour rain forecast |
| "What time is it?" | Current time |
| "What's today's date?" | Current date and day |

---

### 🔍 Search & Web

| You say | What happens |
|---|---|
| "Search for [topic]" | Google search in browser |
| "Open YouTube" | Opens YouTube |
| "Open GitHub" | Opens GitHub |
| "Open [any website]" | Opens that website |

---

### 🎵 Spotify Control

| You say | What happens |
|---|---|
| "Play [song/artist] on Spotify" | Plays on Spotify |
| "What's playing on Spotify?" | Shows current track |
| "Pause Spotify" | Pauses playback |

> Requires Spotify Developer credentials in `.env`.

---

### 📺 YouTube

| You say | What happens |
|---|---|
| "Play [video] on YouTube" | Searches and plays on YouTube |

---

### 📝 Notes & Memory

| You say | What happens |
|---|---|
| "Remember that I like dark mode" | Stores the fact permanently |
| "What do you remember about me?" | Recalls stored facts |
| "Forget that I like dark mode" | Removes that memory |
| "Save a note: [text]" | Saves a text note |

---

### ⏰ Reminders & Timers

| You say | What happens |
|---|---|
| "Remind me in 30 minutes to stretch" | Sets a voice reminder |
| "Set a 25-minute Pomodoro timer" | Starts a focus timer |
| "Add 'finish homework' to my to-do list" | Adds a task |
| "What's on my to-do list?" | Lists pending tasks |
| "Mark task 1 as complete" | Completes a task |

---

### 📅 Calendar (Google Calendar)

| You say | What happens |
|---|---|
| "What's on my calendar today?" | Lists today's events |
| "Add meeting on Friday at 3 PM" | Creates a calendar event |

> Requires a `gmail_credentials.json` file from Google Cloud Console.

---

### 📧 Gmail

| You say | What happens |
|---|---|
| "Read my emails" | Reads latest 5 unread emails |
| "Do I have any emails?" | Checks inbox |

> Requires `gmail_credentials.json`.

---

### 📋 Clipboard AI

| You say | What happens |
|---|---|
| "Translate clipboard" | Translates copied text |
| "Rewrite clipboard" | Rewrites in better English |
| "Summarize clipboard" | Summarizes long copied text |
| "Fix clipboard grammar" | Corrects grammar errors |
| "Read clipboard" | Reads aloud what's copied |

---

### 🖥️ Screen Intelligence & Guiding Friend

| You say | What happens |
|---|---|
| "Look at my screen" / "Screen dekho" | Multimodal vision inspects the screen and gives smart advice |
| "Explain this error" / "Help with this code" | Analyzes your terminal or code editor screen and pinpoints the bug |
| "What am I working on?" | Shin checks active window and screen context to understand your work |
| "Take a screenshot" | Captures screen to disk |
| "Read the screen" / "Screen padho" | OCR reads visible text aloud |
| "Find [word] on screen" | Searches screen for specified text and reports location |

---

### 🏠 Smart Home (Tuya)

| You say | What happens |
|---|---|
| "Turn on the lights" | Controls Tuya smart devices |
| "Activate night mode" | Sets a scene |
| "Are my lights on?" | Checks device status |

> Requires Tuya device credentials in `.env`.

---

### ⚡ System Control & PC Mastery

| You say | What happens |
|---|---|
| "Clean RAM" / "Free RAM" / "RAM saaf karo" | Purges process working sets via Windows PSAPI and reports freed MB |
| "Run PC Manager" / "Boost PC" | Launches Microsoft PC Manager |
| "Clean PC" / "Empty recycle bin" | Empties Recycle Bin and purges Windows temp files without prompt |
| "Open terminal" / "PowerShell kholo" | Launches Windows Terminal / PowerShell at your project directory |
| "Run in terminal: [command]" | Executes PowerShell commands safely, speaks result, and copies to clipboard |
| "What apps are installed?" / "List installed apps" | Deep scans Start Menu, Registry, and UWP Store apps and summarizes |
| "Shut down" | Initiates Windows shutdown |
| "Restart my PC" | Restarts Windows |
| "Sleep" / "Lock screen" | Sleeps or locks PC |
| "I'm going to sleep" | Says "Good night" and **shuts down in 10 seconds** |
| "Brightness up / down" | Adjusts screen brightness |
| "Check system status" | Reports CPU, RAM, battery usage |
| "What processes are running?" | Lists running applications |

---

### 💻 Typing & Keyboard

| You say | What happens |
|---|---|
| "Type [text]" | Types text at cursor position |
| "Press Enter / Escape / Tab" | Simulates key press |
| "Click on [button text]" | Clicks UI element by text |
| "Scroll up / down" | Scrolls the active window |

---

### 🖐️ Hand Gesture Commands

| You say | What happens |
|---|---|
| "Start gesture control" | Activates MediaPipe webcam gesture recognition |
| "Stop gesture control" | Stops gesture recognition and frees webcam |
| "Toggle gesture control" | Toggles hand gesture mode |

#### Recognized Hand Gestures:
- 🖐️ **Open Palm**: Mute System Volume
- ✊ **Fist**: Play / Pause Media Playback
- 👍 **Thumbs Up**: Volume Up (+10%)
- 👎 **Thumbs Down**: Volume Down (-10%)
- ✌️ **Peace / V Sign**: Take Screenshot
- ☝️ **Point Up**: Scroll Up
- 👇 **Point Down**: Scroll Down
- 🤟 **OK / Rock Sign**: Next Track

---

### 📊 Unit Conversion

| You say | What happens |
|---|---|
| "Convert 100 km to miles" | Instant conversion |
| "How much is 5 dollars in rupees?" | Currency conversion |

---

### 🧩 Custom Macros (Shortcuts)

| You say | What happens |
|---|---|
| "Record a shortcut named morning routine" | Starts recording a sequence |
| "Open Chrome → Open YouTube → Play music" | Recorded as steps |
| "Stop recording" | Saves the macro |
| "Run morning routine" | Executes all recorded steps in order |
| "List my shortcuts" | Shows all saved macros |
| "Delete [macro name]" | Removes a macro |

---

### 🔒 Voice Authentication

| You say | What happens |
|---|---|
| "Remember my voice" | Enrolls your voice biometric |
| "Delete my voice profile" | Removes voice security |

When enabled (`VOICE_AUTH_ENABLED=true`), Shin will only respond to you.

---

### 🗣️ Conversation & Personality

| You say | What happens |
|---|---|
| "Hello" / "Namaste" | Greeted warmly |
| "Who are you?" | Shin introduces herself |
| "Who made you?" | Credits MJ as creator |
| "Tell me a joke" | Gets a programming joke |
| "Talk in English" | Switches to English |
| "Talk in Hindi" | Switches to Hindi |
| "Be more formal" | Changes personality style |

---

### 🎓 Deep Knowledge & Concept Explanations (`shin_knowledge.py`)

| You say | What happens |
|---|---|
| "What is VS Code?" / "Explain VS Code" | Explains Microsoft Visual Studio Code, extensions, terminal, LSP |
| "How does the laptop work?" / "Explain laptop" | Explains CPU, RAM, GPU, SSD/storage, motherboard, and Windows OS |
| "What is CPU / RAM / GPU?" | Deep dive into processing cores, clock speed, volatile memory, VRAM |
| "What is an application?" / "What is a browser?" | Explains software programs, binaries vs UWP, browser engines |
| "What is PowerPoint / PPT?" | Explains slide decks, visual hierarchy, presentation tips |
| "What are documents and files?" | Explains file formats (.py, .docx, .pdf, .md), directory paths |
| "What is a command and talk?" | Explains difference between actionable imperative commands and conversational talk |
| "What to answer on command?" | Explains Shin's rule: swift action feedback on commands, rich empathy on talk |

---

### 🔍 App Location & Explorer Reveal (`app_finder.py`)

| You say | What happens |
|---|---|
| "Where is Chrome installed?" | Locates Chrome executable path and highlights in Windows File Explorer |
| "Find where Blender is located" | Resolves shortcut / binary path and opens target folder in Explorer |
| "Locate VS Code" | Speaks exact installation folder and shows executable |

---

### 🛠️ Interactive Training Mode (`commands.py` + `assistant.py`)

| You say | What happens |
|---|---|
| "Train yourself" / "Teach her new things" | Starts 5-phase interactive Q&A interview (15 curated questions) |
| "Teach her how to behave" | Enters behavioral training session |
| [During training] "My full name is MJ" | Records answer into persistent long-term memory (`data/memory.json`) |
| [During training] "Skip" | Skips current question and moves to next |
| [During training] "Stop training" | Pauses training session |
| "What do you know about me?" | Lists saved facts from memory |

---

### 💻 Project & Coding Assistant (`help_with_project`)

| You say | What happens |
|---|---|
| "Help me with my project" | Inspects active workspace (VS Code, Blender, Terminal) and clipboard |
| "Debug my code" / "Review this code" | Checks clipboard for code/error tracebacks and provides instant fixes |
| "Check screen error" / "Diagnose screen bug" | Scans screen for Python tracebacks, npm errors, or compiler warnings |

---

### 👁️ Screen Understanding & Vision Perception (`vision.py`)

| You say | What happens |
|---|---|
| "What is happening on screen?" | Multimodal AI or rule-based analysis describes active workspace |
| "Look at my screen" / "Dekh screen pe" | Spoken summary of active window, application category, and work focus |
| "Check screen error" | Specifically looks for visible bugs, syntax errors, or app crashes |

---

### ⚡ Code Generation & Python Execution (`clipboard_ai.py` + `commands.py`)

| You say | What happens |
|---|---|
| "Write Python code for calculator" | Generates clean, robust Python code and copies to clipboard |
| "Explain this code" / "Code samjhao" | Reads clipboard code and explains architecture/logic in plain Hinglish |
| "Run python code: print('hello')" | Safely executes Python snippet in project workspace, returns stdout or copies output |
| "Python code run karo: 2 + 2" | Quick Python calculation / script testing |

---

### 🌿 Git & Project Repository Intelligence (`commands.py`)

| You say | What happens |
|---|---|
| "Check git status" / "Git status kya hai" | Speaks current branch, number of modified, staged, untracked, and deleted files |
| "Git diff" / "Explain git diff" | Inspects recent uncommitted changes and copies `--stat` summary to clipboard |
| "Create file test_model.py" | Creates a new file in the project workspace, optionally pasting clipboard code |
| "Naya file banao utils.py" | Instantly writes code from clipboard into the new file |

---

### 💬 WhatsApp Smart Drafting & Messaging (`commands.py`)

| You say | What happens |
|---|---|
| "Send a message to Dad saying I am home" | Opens WhatsApp desktop/web and sends the message |
| "Draft WhatsApp message to Dad saying I reached college" | Composes a natural, polite Hinglish/English message and copies to clipboard |
| "Draft a message saying I will be late" | Prepares ready-to-paste text without sending automatically |
| "Open WhatsApp chat with [name]" | Direct deep link into conversation |

---

### 🛡️ Automated Code Reviewer & Enterprise Compliance (`scanner.py` + `commands.py`)

| You say | What happens |
|---|---|
| "Review this code" / "Code review karo" | Scans clipboard code for broad exceptions, SQL injections, hardcoded secrets, and style flaws |
| "Review file order_service.py" | Scans local Python/JS file using AST/regex scanner and speaks findings |
| Antigravity Skill: "Review @your_file.py" | Triggers the `.agents/skills/code-reviewer/` skill to generate a structured markdown report |

---

### 🧠 2026 AI PC, NPU & Hardware Diagnostics (`ai_hardware.py`)

| You say | What happens |
|---|---|
| "Check AI hardware" / "Check NPU" | Scans WMI for Neural Processing Units (NPUs), checks Copilot+ PC (40+ TOPS) readiness |
| "Is my laptop Copilot ready?" | Audits NPU, GPU VRAM, DirectML / ONNX capability, and estimated LLM decode token speed |
| "What is NPU?" | Deep explanation of 1-5W power envelopes, matrix multiplication, Block FP16 vs INT8 |

---

### 🌲 Windows UIAutomation Accessibility Tree (`ui_tree.py`)

| You say | What happens |
|---|---|
| "Get UI controls" / "Screen pe kaunse buttons hain" | Reads all interactive buttons, inputs, tabs, and menus in the foreground window with 0-token cost |
| "Click button Save" / "Click on Submit" | Programmatically locates the control and triggers a deterministic click with zero hallucination |

---

### 🔌 Model Context Protocol (MCP Server: `core/mcp_server.py`)
Shin exposes her full tool registry as a standard JSON-RPC 2.0 MCP server for Antigravity, Claude Desktop, and IDE agents:
- `shin_inspect_screen`: Screen perception and error diagnosis
- `shin_get_ui_tree`: Windows UIAutomation control tree extraction
- `shin_click_ui_element`: Deterministic button clicking
- `shin_run_python_code`: Safe Python execution
- `shin_review_code`: Security and anti-pattern static scanning
- `shin_check_git_status`: Git repository monitoring

---

### 🔒 CaMeL Dual-LLM Defense (`core/security_shield.py`)
Protects Shin from Visual Prompt Injection (VPI) and Branch Steering attacks when reading web pages, emails, and OCR text by sanitizing untrusted inputs before they reach the planning model.

### 🌐 News

| You say | What happens |
|---|---|
| "Tell me the news" | Reads top world headlines |

> Requires `WORLD_NEWS_API_KEY` in `.env`.

---

### 🔄 Wi-Fi, Bluetooth & Settings

| You say | What happens |
|---|---|
| "Turn on Wi-Fi" | Enables Wi-Fi |
| "Turn off Bluetooth" | Disables Bluetooth |
| "Enable airplane mode" | Enables airplane mode |
| "Turn on night light" | Enables Windows Night Light |
| "Enable mobile hotspot" | Starts mobile hotspot |

---

## Proactive Senses (Alerts)

Shin runs proactive background monitoring and speaks alerts without you asking.

All alerts are handled by [`alerts.py`](core/alerts.py) in a background thread.
All spoken lines are **randomised** every time using the personality engine — she never says the same phrase twice:

| Alert | Condition | Example phrase |
|---|---|---|
| **Low Battery** | Below 20%, 15%, or 10% | *"MJ, battery low hai — charger lagao!"* |
| **Power Connected** | Charger plugged in | *"Charger laga diya! Battery charge ho rahi hai."* |
| **High CPU** | CPU > 85% for 50 seconds | *"Warning: CPU usage has been very high."* |
| **Bedtime Reminder** | After 12:00 AM | *"Yaar, so jao ab! Bahut raat ho gayi."* (once per night) |
| **Water Reminder** | Every 1 hour | *"Paani piyo, MJ!"* / *"Ek glass paani pi lo please."* |
| **Eye Break** | Every 30 minutes | *"Aankhein rest do thoda, MJ!"* |
| **Lunch Alert** | 1:30 PM – 2:30 PM | *"Khaana khaya kya, MJ?"* (once per day) |
| **Dinner Alert** | 8:30 PM – 9:30 PM | *"Dinner time! Kuch kha lo."* (once per day) |
| **Calendar Events** | 15 minutes before | *"MJ, heads up! You have: [event] in X minutes."* |
| **To-Do Nudge** | Every 2 hours (if tasks pending) | *"MJ, yaad dilana tha — abhi bhi 3 pending tasks hain!"* |
| **Coding Nudge** | After 1 hour in VS Code | *"Bhai, ek ghante se code kar rahe ho — stretch karo!"* |
| **Blender Nudge** | After 1 hour in Blender | *"Ek ghante se Blender chal raha hai! Aankhein rest do."* |
| **Gaming Silencer** | Game window active | All non-critical alerts suppressed |
| **Return from Idle** | Mouse moved after 10 min idle | *"Wapas aa gaye! Ready ho jaate hain."* |
| **Process Done** | Watched process exits | *"MJ, process [name] has finished executing."* |
| **Random Chatter** | Every 15–25 min randomly | *"Aaj bahut kaam kiya. Proud of you!"* (silent in logs) |

---

## AI Backends

Shin uses a **3-tier AI pipeline** for understanding commands:

```
Tier 1: Rule-Based Regex (fastest, always works offline)
   ↓ (no match)
Tier 2: Cloud AI (OpenAI GPT-4o-mini or Google Gemini 2.0 Flash)
   ↓ (no API key or network error)
Tier 3: Local Ollama LLM (fully offline, privacy-first)
   ↓ (no Ollama installed)
Returns: "unknown" intent
```

### NLP Tiers Explained

| Tier | Module | Requires | Speed |
|---|---|---|---|
| Rule-based | `nlp.py` `_RULES` | Nothing | < 1 ms |
| OpenAI GPT-4o-mini | `nlp.py` `_ai_parse` | `OPENAI_API_KEY` | ~500 ms |
| Google Gemini | `nlp.py` `_ai_parse` | `GEMINI_API_KEY` | ~400 ms |
| Ollama (local) | `nlp.py` `_ai_parse` | Ollama installed | ~1–3 s |

### 🧠 Situational Awareness in AI Fallback (Tiers 2 & 3)
When a command is forwarded to the AI backends, Shin dynamically builds a **Situational Context** block. This enables the AI to respond contextually and naturally instead of acting like a rigid machine.

The context payload includes:
- **Current Time & Day**: Knowing if it's morning, lunchtime, late night, or a weekend.
- **Shin's Current Mood**: Based on recent user interactions (tired, happy, concerned, excited).
- **Active App**: The application MJ is currently using in the foreground.
- **Command History**: The last 3 commands MJ executed, giving the AI immediate short-term memory.

---

## Voice & Speech Settings

### Speech Recognition (ASR) Options

| Setting | Value | Description |
|---|---|---|
| `ASR_BACKEND` | `google` | Google Speech API (online, very accurate) |
| `ASR_BACKEND` | `vosk` | Vosk local model (fully offline) |
| `ASR_BACKEND` | `whisper` | OpenAI Whisper local model (offline, GPU recommended) |
| `ASR_LANGUAGE` | `auto` | Auto-detect Hindi/English |
| `ASR_LANGUAGE` | `hi-IN` | Force Hindi recognition |
| `ASR_LANGUAGE` | `en-US` | Force English recognition |

### Text-to-Speech (TTS) Options

| Setting | Value | Description |
|---|---|---|
| `TTS_BACKEND` | `edge` | Microsoft Edge Neural TTS (online, high quality) |
| `TTS_BACKEND` | `pyttsx3` | Windows SAPI offline voice (no internet needed) |
| `EDGE_TTS_VOICE` | `hi-IN-SwaraNeural` | Hindi female (default) |
| `EDGE_TTS_VOICE` | `hi-IN-MadhurNeural` | Hindi male |
| `EDGE_TTS_VOICE_EN` | `en-US-EmmaNeural` | English female (default) |
| `EDGE_TTS_VOICE_EN` | `en-US-GuyNeural` | English male |

> [!IMPORTANT]
> **Intelligent Script Routing**:
> All Romanized Hinglish text written in Latin/English characters (e.g. *"Subah ho gayi!"* or *"Haan, kar deti hoon!"*) is automatically routed to the **English TTS voice** (`en-US-EmmaNeural`). The English voice reads Latin Hinglish perfectly and naturally. The **Hindi TTS voice** (`hi-IN-SwaraNeural`) is reserved strictly for actual Devanagari characters (e.g. *"सुबह हो गई"*), preventing the Hindi voice from mispronouncing English letters phonetically.

### Offline Fallback Behavior

When no internet is detected:
1. **ASR**: Automatically falls back from Google → Vosk (if model downloaded)
2. **TTS**: Automatically falls back from Edge Neural → pyttsx3 (within 3 seconds)

---

## Security Guardrails

Shin includes a command safety validator in `commands.py` that **blocks dangerous operations** before executing them.

### Blocked Actions:

| Category | Blocked Examples |
|---|---|
| **Destructive executables** | `regedit`, `diskpart`, `format` |
| **Dangerous scripts** | Files with `.bat`, `.cmd`, `.vbs`, `.js`, `.ps1`, `.reg`, `.scr`, `.sh` extensions |
| **File deletion commands** | `rm -rf`, `rmdir /s`, `rd /s /q`, `del /f` |
| **Registry modification** | `reg delete`, `reg add` |
| **SQL destruction** | `DROP TABLE`, `DROP DATABASE` |

If a blocked command is detected, Shin says: **"Access denied. [Reason]"** and does nothing.

---

## Developer Guide

### Running Tests

```powershell
.\.venv\Scripts\python -m pytest tests/ -v
```

All 145 tests should pass. Tests cover:
- Intent parsing for all command categories
- Security guardrail blocking
- Sleep/shutdown command detection
- Voice auth bypass for special commands

---

### Personality & Mood System

All of Shin's spoken personality lives in [`personality.py`](core/personality.py). This is the **only** place you need to edit to change how she sounds.

#### Adding new phrase variants

Open `core/personality.py` and find the `_POOLS` dictionary. Add more strings to any existing pool:

```python
_POOLS = {
    "done": [
        "Ho gaya!",
        "Done!",
        "All set!",
        "Your new phrase here!"  # ← just add to the list
    ],
    ...
}
```

The `pick(category)` function auto-ensures no phrase repeats back-to-back.

#### Updating her mood

From any module:
```python
import personality
personality.update_mood("user_tired")   # → concerned
personality.update_mood("gaming")        # → excited
personality.update_mood("task_done")     # → happy
personality.get_mood()                   # → "happy"
```

#### Available Mood Triggers

| Trigger | Mood result |
|---|---|
| `late_night` | tired |
| `morning` / `afternoon` / `evening` | normal |
| `task_done` | happy |
| `user_tired` | concerned |
| `user_happy` | happy |
| `user_sad` | concerned |
| `gaming` | excited |
| `long_session` | concerned |

#### Personality API Reference

| Function | Returns | Description |
|---|---|---|
| `pick("done")` | `str` | Random non-repeating phrase from pool |
| `get_thinking_prefix(intent)` | `str` | "Searching..." etc. for an intent type |
| `get_startup_greeting(hour)` | `str` | Varied time-of-day greeting |
| `get_random_observation()` | `str` | Context-aware proactive one-liner |
| `update_mood(trigger)` | `None` | Update Shin's internal mood state |
| `get_mood()` | `str` | Read current mood |

---

### Project Modules Reference

| Module | Purpose |
|---|---|
| `assistant.py` | Entry point, TTS worker, ASR loop, startup greeting, personality init |
| `core/personality.py` | **★ Mood engine, response pools, Hinglish phrases, random chatter** |
| `core/nlp.py` | Intent parsing (rules → AI → Ollama) + emotional keyword detection |
| `core/commands.py` | Windows action handlers for every intent |
| `core/alerts.py` | Background monitoring + varied proactive alerts + random small talk |
| `core/weather.py` | OpenWeatherMap weather fetching |
| `core/memory.py` | Persistent JSON memory store |
| `core/macros.py` | Record and playback custom shortcuts |
| `core/voice_auth.py` | Speaker verification (Resemblyzer embeddings) |
| `core/vision.py` | OCR screen reading (pytesseract + PIL) |
| `core/calendar_ai.py` | Google Calendar API read/write |
| `core/gmail_ai.py` | Gmail inbox reading |
| `core/spotify_ai.py` | Spotify playback via spotipy |
| `core/clipboard_ai.py` | AI-powered clipboard transformations |
| `core/clipboard_history.py` | Background clipboard change monitor |
| `core/smart_home.py` | Tuya IoT device control |
| `core/todo.py` | JSON-backed to-do list |
| `core/news.py` | World News API fetcher |
| `core/token_tracker.py` | API token usage logging |
| `core/ui_server.py` | HTTP + WebSocket server for the 3D Orb |
| `core/orb_window.py` | Electron orb overlay launcher |
| `core/command_log.py` | Command history log to JSON |
| `core/api_manager.py` | API key validation utility |

### Adding a New Command

1. **Add a rule in `nlp.py`** (in the `_RULES` list):
```python
(
    r"\b(?:say hello to|greet)\s+(.+)\b",
    lambda m: {"intent": "custom_greet", "args": {"name": m.group(1).strip()}},
),
```

2. **Add the handler in `commands.py`** (in the `dispatch()` function):
```python
elif intent == "custom_greet":
    name = args.get("name", "world")
    return f"Hello there, {name}! Nice to meet you."
```

3. **Add to `_KNOWN_INTENTS` set** in `nlp.py`:
```python
"custom_greet",
```

---

## Built With

| Library | Purpose |
|---|---|
| `speech_recognition` | Google ASR microphone input |
| `vosk` | Offline speech recognition |
| `edge-tts` | Microsoft Neural TTS (online) |
| `pyttsx3` | Offline TTS fallback |
| `pygame` | Audio playback for TTS mp3 files |
| `pyautogui` | Mouse/keyboard automation |
| `psutil` | System info (battery, CPU, RAM) |
| `pywin32` | Deep Windows API integration |
| `pycaw` | Per-app audio volume control |
| `resemblyzer` | Voice biometric speaker verification |
| `noisereduce` | Microphone noise cancellation |
| `schedule` | Background task scheduling |
| `websockets` | Real-time Orb UI communication |
| `Flask` | Local HTTP server for Orb UI |
| `openai` | GPT-4o-mini NLP fallback |
| `google-genai` | Gemini NLP fallback |
| `spotipy` | Spotify API control |
| `pytesseract` | Screen OCR |
| `pystray` | Windows system tray icon |
| `colorama` | Colored terminal output |

---

## Troubleshooting

| Problem | Solution |
|---|---|
| "Shin listens but doesn't respond" | Check internet connection. Try setting `ASR_BACKEND=vosk` for offline mode. |
| Vosk model fails to load | Make sure model folder contains `am/` and `conf/` subfolders. Shin auto-resolves double-nested zips. |
| Edge TTS hangs when offline | Shin now has a 3-second timeout and auto-switches to pyttsx3. |
| PyAudio install fails | Run `pipwin install pyaudio` or install from a .whl file. |
| Weather says "name 'extra' is not defined" | Already fixed in current version. |
| No speech detected at all | Check microphone permissions in Windows Settings → Privacy → Microphone. |
| Shin doesn't understand Hindi | Set `ASR_LANGUAGE=hi-IN` and `ASR_BACKEND=google` or use `vosk-model-hi-0.22`. |
| Shin mispronounces Hinglish (Hindi written in English letters) | Already fixed in the current version. Shin automatically routes all Latin-script Hinglish text to the English voice (`en-US-EmmaNeural`) which reads it naturally, and reserves the Hindi voice (`hi-IN-SwaraNeural`) for Devanagari script. |
| Too many false wake word triggers | Lower mic sensitivity or increase `SR_ENERGY_THRESHOLD` in `.env`. |

---

## License

This project was created by **MJ** (Meharaj SohabatAli Ansari) for personal use.  
ENTC Student · D.Y. Patil School of Engineering and Management, Kolhapur.

---

*Shin — Always on. Always listening. Always ready.*
