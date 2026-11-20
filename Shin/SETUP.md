# 🎙️ Shin Voice Assistant & 3D Desktop Companion — Setup Guide

> Welcome to **Shin**! A Windows-native AI voice assistant and interactive 3D desktop companion with a living Hinglish/English personality.  
> Say **"Hey Shin"** to activate — she talks naturally, responds to commands, adapts to your mood, checks in on you, and drives both a **3D Desktop Mascot Avatar** and **Windows Dynamic Island**.

---

## 📋 System Requirements

| Component | Requirement |
|---|---|
| **Operating System** | Windows 10 or Windows 11 (64-bit) |
| **Python Version** | **Python 3.10, 3.11, or 3.12** *(Recommended: Python 3.12)*<br>⚠️ *Note: Python 3.14+ is NOT supported yet because pre-compiled binary wheels for PyAudio and PyTorch are not available for 3.14.* |
| **Audio** | Working microphone and speakers / headphones |
| **Graphics** | Any modern GPU (Integrated Intel/AMD or Dedicated NVIDIA/AMD) |
| **Internet** | Optional for online Google ASR & Edge Neural TTS. Shin also includes offline speech & intent models! |

### 📥 Installing Python 3.12 (If you don't have it)
1. Download Python 3.12 from the official website:  
   👉 **[Download Python 3.12 (Windows 64-bit Installer)](https://www.python.org/downloads/release/python-3128/)**
2. Run the installer.
3. ⚠️ **VERY IMPORTANT:** Check the box at the bottom: **"Add python.exe to PATH"** before clicking "Install Now".

---

## ⚡ Quick 1-Click Setup

1. **Extract the ZIP archive** to a folder on your computer (for example: `C:\Shin` or `D:\Shin`).  
   *(Tip: Avoid deeply nested or read-only folders).*
2. Open the folder and simply **double-click `setup.bat`** (or open `Shin\` and run `setup.bat`).

### What `setup.bat` does automatically:
- Finds your Python 3.10–3.12 installation.
- Creates an isolated virtual environment (`.venv`).
- Pre-installs pre-compiled audio binaries (`PyAudio`, `webrtcvad`).
- Installs all required dependencies from `requirements.txt`.
- Prepares your default `.env` configuration file.

*The setup takes about 2 to 5 minutes depending on your internet connection.*

---

## ⚙️ Configuration (`.env`)

Shin works **100% out of the box** without any paid API keys!
- **Speech Recognition:** Free Google Speech Recognition (online) + Vosk (bundled offline models).
- **Speech Output:** Free Microsoft Edge Neural Voices (`en-IN-NeerjaNeural` Indian English & `hi-IN-SwaraNeural` Hindi) + Windows SAPI (`pyttsx3`).
- **Intent Understanding:** Bundled offline neural intent classifier (`data/neural_intent_model.pth`).

### Optional: Add Smart AI Brains (ChatGPT / Gemini / Groq / Ollama)
If you want Shin to answer complex coding, knowledge, or conversational queries like ChatGPT, open the `.env` file in Notepad:

```powershell
notepad Shin\.env
```

| Setting | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(empty)* | Free Google Gemini API Key from [Google AI Studio](https://aistudio.google.com/app/apikey). Highly recommended! |
| `GROQ_API_KEY` | *(empty)* | Ultra-fast free cloud LLM inference from [Groq Cloud](https://console.groq.com). |
| `OPENAI_API_KEY` | *(empty)* | OpenAI API key from [platform.openai.com](https://platform.openai.com). |
| `OLLAMA_MODEL` | `llama3.2:3b` | Offline private LLM. Download from [ollama.com](https://ollama.com) and run `ollama pull llama3.2:3b`. |
| `WEATHER_CITY` | `Mumbai` | Set to your city name (e.g. `Delhi`, `Pune`, `Kolhapur`, `Bengaluru`, `London`). |
| `DISABLE_MASCOT` | `false` | Set to `true` if you want a lightweight background assistant without the 3D Unity avatar to save RAM. |

---

## 🚀 How to Launch Shin

You have three convenient ways to run Shin:

### 1. Background Mode (Recommended for Daily Use)
Double-click **`start_shin.bat`**.
- Shin starts silently in the background.
- A **cyan circle icon** appears in your Windows System Tray (near the clock).
- The **3D Mascot Companion** (`MateEngineX.exe`) launches automatically on your desktop!

### 2. Desktop Shortcut
Double-click **`create_desktop_shortcut.bat`**.
- This creates a **Shin Assistant** shortcut icon right on your Windows Desktop.
- You can double-click that shortcut anytime to start Shin!

### 3. Foreground / Console Mode (For Testing & Viewing Logs)
Open a terminal in the Shin directory and run:
```powershell
.\.venv\Scripts\Activate.ps1
python Shin\assistant.py
```
*(Or inside the `Shin\` folder: `python assistant.py`)*

This displays live speech recognition transcripts, intent recognition scores, and system events in real-time.

---

## 🛑 How to Stop Shin

- **Option A:** Double-click **`stop_shin.bat`**.
- **Option B:** Right-click the **cyan circle icon** in your Windows System Tray (bottom right near the clock) and click **"Quit Shin"**.

---

## 🗣️ Voice Commands to Try

Say **"Hey Shin"** (or in continuous mode, just speak):

| Category | Example Voice Commands |
|---|---|
| **Chit-Chat & Persona** | *"Hey Shin, kaise ho?", "Who are you?", "Tell me a joke", "Mera mood off hai"* |
| **3D Mascot Control** | *"Shin dance", "Hide avatar", "Show avatar", "Reset avatar position"* |
| **Apps & Windows** | *"Open Chrome", "Close Notepad", "Launch VS Code", "Open YouTube", "Switch to Spotify"* |
| **Volume & Media** | *"Volume 50 karo", "Volume up", "Mute", "Play lo-fi on YouTube", "Next track"* |
| **Weather & News** | *"What's the weather today?", "Aaj baarish hogi kya?", "Read the news"* |
| **System & Battery** | *"Check battery", "Lock the screen", "Take a screenshot", "What time is it?"* |
| **Clipboard AI** | *"Translate clipboard", "Summarize what I copied", "Fix grammar in clipboard"* |
| **Reminders & Tasks** | *"Remind me to drink water at 4 PM", "Add task finish homework", "What are my tasks?"* |
| **Memory** | *"Remember that I love coding in Python", "What do you know about me?", "Forget that"* |

---

## 🛠️ Troubleshooting & FAQ

### Q1: Setup says `[ERROR] Compatible Python (3.10 - 3.12) not found`
- **Cause:** You either don't have Python installed, or you are running Python 3.14+ (which currently lacks pre-built wheels for PyAudio, PyTorch, and Vosk).
- **Fix:** Install Python 3.12 from [Python 3.12 Installer](https://www.python.org/downloads/release/python-3128/). Make sure to check **"Add python.exe to PATH"** during setup, then run `setup.bat` again.

### Q2: PowerShell says `running scripts is disabled on this system` (ExecutionPolicy)
- **Fix:** Simply run **`setup.bat`** (the `.bat` file automatically bypasses the policy).  
  Alternatively, open PowerShell as Administrator and run:
  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  ```

### Q3: Shin does not hear my voice or fails on audio input
- **Fix:**
  1. Go to Windows **Settings → Privacy & Security → Microphone**.
  2. Ensure **"Microphone access"** and **"Let apps access your microphone"** are turned **ON**.
  3. Ensure your microphone is set as the Default Input Device in Windows Sound Settings.

### Q4: How do I disable the 3D Desktop Mascot to save RAM?
- Open `Shin\.env` in Notepad and change:
  ```env
  DISABLE_MASCOT=true
  ```
- Save the file and restart Shin. Shin will run as a lightweight, low-RAM background assistant.

### Q5: How do I use Shin completely offline without internet?
- In `Shin\.env`:
  ```env
  ASR_BACKEND=vosk
  TTS_BACKEND=pyttsx3
  ```
- Shin will use the included Vosk models in `languages/` for speech recognition and Windows SAPI for speech output!

---

## ❤️ Credits & Acknowledgments
- **Creator:** MJ (ENTC, D.Y. Patil School of Engineering and Management)
- **Technologies:** Python, PyTorch, Edge-TTS, Vosk, Unity (MateEngineX), Windhawk (Dynamic Island), pywebview.

Enjoy using your new personal AI assistant! If you have any questions or feedback, reach out to MJ! 🚀
