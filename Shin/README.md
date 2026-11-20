# Shin — Personal AI Voice Assistant & Desktop Companion

> A fully offline-capable, Windows-native AI voice assistant and 3D desktop companion with a living personality.  
> Say **"Hey Shin"** to activate — she responds in Hinglish, adapts to your mood, thinks out loud, proactively checks in on you, and drives both a **Windows Dynamic Island** and a **3D Desktop Avatar (Mate Engine)**.

---

## ✨ What Makes Shin Special

| Feature | Description |
|---|---|
| 🎭 **Living Personality** | Random Hinglish phrases, varied startup greetings, and a warm, caring best-friend tone |
| 🔄 **Continuous Conversational Flow** | ChatGPT Voice / Gemini Live-style multi-turn dialogue with continuous follow-up listening (no wake-word fatigue) and natural exit detection |
| 🏝️ **Windows Dynamic Island** | Native C++ Windhawk Mod integration via high-speed named pipes (`\\.\pipe\ShinDynamicIsland`) displaying live speech states, weather, music, and notifications |
| 💃 **3D Mate Engine Companion** | Integrated with 3D VRM desktop avatar (`MateEngineX.exe`) for real-time lip-sync, talking animations, dance modes, and synchronized chat bubbles |
| ⏱️ **Proactive Heartbeat & Timemap** | DesktopFriends-inspired semantic daily scheduler with a 60-second zero-cost local ticker for autonomous reminders, greetings, and break prompts |
| 🧠 **Cognitive Reasoning** | `innerThought` for internal thoughts displayed on Dynamic Island / UI and `shouldReply` decision logic for subtle gestures vs vocal replies |
| 💬 **Thinks Out Loud** | Says *"Searching..."* or *"Ek second..."* with mood & live environmental context injection (weather, active app, battery, time) |
| 📴 **Fully Offline & Multi-Model** | Works completely offline (Vosk ASR + pyttsx3 TTS + Ollama) or online (Google ASR, Edge Neural TTS, Gemini, OpenAI, Claude) |
| 🛡️ **Safety Guardrails** | Blocks destructive system commands (`format`, `regedit`, `rm -rf`, fork bombs, etc.) |
| 🖐️ **Hand Gesture Control** | Real-time MediaPipe webcam hand gestures for volume, media playback, scrolling, and screenshots |
| 🔒 **Voice Biometrics** | Speaker verification using Resemblyzer to respond only to your enrolled voice |
| 💤 **Smart Sleep & Tray Minimization** | Minimizes to Windows system tray, background watchdog persistence, and auto-sleep shutdown |

---

## 🗣️ Example Commands

| Category | Say this |
|---|---|
| **Conversational Flow** | "Hey Shin, what should I work on today?" → *(Shin answers, then keeps listening without requiring wake-word)* → "Also check my schedule" → "Thanks, that's all" |
| **Desktop Companion** | "Shin dance", "Hide avatar", "Show avatar", "Reset avatar position" |
| **App Control** | "Open Chrome", "Close Spotify", "Launch Notepad", "Switch to VS Code" |
| **Volume & Media** | "Mute", "Volume up", "Set volume to 60", "Play next track" |
| **System** | "Lock the screen", "Check battery", "I'm going to sleep", "Restart" |
| **Web & Research** | "Search Python async tutorials", "Open github.com", "Read the news" |
| **Clipboard AI** | "Translate clipboard", "Summarize what I copied", "Fix grammar" |
| **Notes & Timemap** | "Remind me to drink water at 3 PM", "Add task finish report", "What's on my schedule?" |
| **Weather & Context** | "What's the weather?", "Will it rain today?", "How's the temperature outside?" |
| **Spotify AI** | "Play lo-fi on Spotify", "What song is playing?", "Pause music" |
| **Macros & Automation** | "Start morning routine", "Record a shortcut called study mode" |
| **Memory** | "Remember that I prefer dark mode", "What do you know about me?", "Forget dark mode" |
| **Hand Gestures** | "Start gesture control", "Stop gesture control", "Toggle gesture control" |
| **Hinglish Actions** | "Volume badhao", "Chrome kholo", "Mujhe 30 minutes mein yaad dilao", "Kaise ho?" |

---

## 🏗️ Architecture & Integrations

```
                                  ┌─────────────────────────────┐
                                  │      Shin Assistant Core    │
                                  │    (assistant.py & NLP)     │
                                  └──────────────┬──────────────┘
                                                 │
                  ┌──────────────────────────────┼──────────────────────────────┐
                  ▼                              ▼                              ▼
      ┌───────────────────────┐      ┌───────────────────────┐      ┌───────────────────────┐
      │  Dynamic Island Mod   │      │   Mate Engine (3D)    │      │  Conversation Engine  │
      │ • C++ Windhawk Mod    │      │ • Unity 6 Desktop App │      │ • Continuous Flow     │
      │ • Named Pipe IPC      │      │ • VRM Lip-Sync & Body │      │ • Heartbeat & Timemap │
      │ • Status & Weather    │      │ • Speech Bubbles (UI) │      │ • Cognitive Tools     │
      └───────────────────────┘      └───────────────────────┘      └───────────────────────┘
```

---

## ⚡ Quick Start

### 1. Prerequisites

- Windows 10 or 11
- Python 3.10 – 3.12
- Working microphone and audio output
- *(Optional)* Windhawk for Dynamic Island Mod
- *(Optional)* Internet for Gemini/OpenAI API + Edge Neural TTS

### 2. One-Click Setup

```powershell
.\setup.ps1
```

This creates a virtual environment (`.venv`), installs all dependencies, and creates your `.env` configuration file.

### 3. Configure

Edit `.env` or set your preferred options:

```powershell
notepad .env
```

| Variable | Default | What it does |
|---|---|---|
| `ASR_BACKEND` | `google` | `google` (online) or `vosk` (offline) |
| `TTS_BACKEND` | `edge` | `edge` (online neural) or `pyttsx3` (offline) |
| `WAKE_WORD` | `hey shin` | Wake-word trigger phrase |
| `WEATHER_CITY` | `Mumbai` | Default city for weather reports |
| `MATE_ENGINE_ENABLED` | `true` | Auto-launches & manages Mate Engine 3D avatar |
| `GEMINI_API_KEY` | *(empty)* | Google Gemini API key for smart conversational reasoning |
| `OPENAI_API_KEY` | *(empty)* | OpenAI API key fallback |
| `OLLAMA_MODEL` | `llama3` | Local offline model name for Ollama |

---

### 4. Running Shin

**Foreground Mode** (ideal for testing and viewing logs):
```powershell
.venv\Scripts\Activate.ps1
python assistant.py              # runs with default configuration
python assistant.py --wake       # forces wake-word detection
python assistant.py --no-wake    # continuous listening mode (test flow)
python assistant.py --debug      # verbose debug and IPC logs
```

**Background Daemon Mode**:
Double-click `start_shin.bat` in the project root folder, or run:
```powershell
.\start_shin.bat
```

To stop Shin, right-click the **cyan circle icon** in your Windows System Tray and choose **"Quit Shin"**, or run `.\stop_shin.bat`.

---

## ☁️ Hybrid Cloud Architecture (Dual-Mode)

Shin supports running in **Hybrid Cloud Mode**, where the AI Brain (FastAPI, WebSockets, NLP intent routing, multi-turn LLM cascade, and memory) runs 24/7 on a cloud platform (Railway, Render, Fly.io, or Docker VPS), while your local Windows PC client handles mic/speakers, **Mate Engine 3D Avatar**, and **Windhawk Dynamic Island**.

### Modes (`.env`):
```ini
# Run completely local on your Windows PC (default)
SHIN_MODE=standalone

# OR run in Hybrid Cloud mode
SHIN_MODE=hybrid
SHIN_CLOUD_URL=https://your-shin-brain.up.railway.app
SHIN_API_KEY=your-secret-token
```

### 1-Click Cloud Deployment:
* **Railway:** Connect your GitHub repo; it automatically detects `railway.toml` and `Dockerfile`.
* **Render:** Add using `render.yaml`.
* **Docker Compose:**
  ```bash
  docker compose up -d
  ```

---

## 📂 Project Structure

```
Shin/
├── assistant.py               # Main runtime loop: wake word, ASR, TTS, continuous flow & IPC
├── requirements.txt           # Python dependencies
├── setup.ps1                  # One-click Windows setup script
├── .env.example               # Config template
├── start_shin.bat             # Background launcher
├── stop_shin.bat              # Clean shutdown utility
├── config/
│   └── conversation_flow.json # Persona settings, follow-up timeouts, exit phrases & brevity
├── core/
│   ├── conversation_flow.py   # Continuous conversation manager, barge-in & dynamic prompts
│   ├── mate_bridge.py         # Mate Engine lifecycle, window positioning & avatar dance IPC
│   ├── island_bridge.py       # Named pipe client for Windows Dynamic Island
│   ├── personality.py         # Shin's living Hinglish personality & mood engine
│   ├── nlp.py                 # Multi-tier NLP engine (rules → Gemini/OpenAI → Ollama)
│   ├── llm_router.py          # Unified LLM provider routing and streaming
│   ├── commands.py            # Windows OS automation handlers & safety gates
│   ├── alerts.py              # Proactive background monitoring (battery, hydration, rest)
│   ├── weather.py             # Open-Meteo & OpenWeatherMap weather engine
│   ├── memory.py              # Long-term persistent key-fact storage
│   ├── macros.py              # Custom macro recording & execution
│   ├── voice_auth.py          # Resemblyzer speaker verification
│   ├── vision.py              # Screen OCR and visual context
│   ├── spotify_ai.py          # Spotify API playback integration
│   ├── calendar_ai.py         # Google Calendar assistant integration
│   ├── gmail_ai.py            # Gmail inbox reader
│   ├── clipboard_ai.py        # AI clipboard actions (summarize, fix grammar, translate)
│   ├── todo.py                # Todo and task list management
│   ├── news.py                # Live news feed client
│   └── ui_server.py           # WebSocket server for 3D Orb UI & desktop bridges
├── mate engin/                # 3D Unity Desktop Companion application (MateEngineX.exe)
├── ui/
│   └── orb.html               # 3D WebGL reactive audio orb overlay
├── data/                      # Auto-created runtime cache (memory, position, macros)
└── tests/                     # 417 passing unit and integration tests
```

---

## 🧪 Tests & Verification

Run the full test suite across all modules:

```powershell
.venv\Scripts\python.exe -m pytest tests/ -v
```

All **417 tests pass** covering:
- Conversation flow & continuous follow-up sessions
- Mate Engine process lifecycle & IPC bridges
- Dynamic Island pipe communication & encoding
- Intent parsing, Hinglish actions, and security hardening
- Voice biometrics, offline ASR/TTS fallbacks, and memory persistence

---

*Built by MJ — ENTC Student, D.Y. Patil School of Engineering and Management, Kolhapur.*
