"""
test_voice_pitch.py — Interactive Voice & Pitch Tuning Tool for Shin
====================================================================
Use this tool to audition voices (Swara, Neerja, Jenny, etc.) and
fine-tune the exact pitch (+Hz / -Hz) to match your friend from Ichalkaranji!
"""

import asyncio
import os
import re
import sys
import time
import tempfile
import subprocess
from pathlib import Path

try:
    import edge_tts
    import pygame
except ImportError:
    print("\n[!] 'edge-tts' or 'pygame' is not installed yet.")
    print("    Installing edge-tts and pygame now via pip...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "edge-tts", "pygame"])
    import edge_tts
    import pygame

ENV_PATH = Path(__file__).parent / ".env"
if not ENV_PATH.exists():
    ENV_PATH = Path(__file__).parent / "Shin" / ".env"

# Her authentic signature lines:
SAMPLE_HINGLISH = "Ki tujhe nahi malum tha kya, aur kya MJ! Bol na kaisa laga mera aawaz?"
SAMPLE_ENGLISH = "Ki tujhe nahi malum tha kya? Of course I speak fluent English too, aur kya MJ!"


def play_audio_file(file_path: str):
    """Play audio cleanly on Windows without COM lockup."""
    # 1. Try Pygame if available
    try:
        import pygame
        pygame.mixer.init()
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.set_volume(0.95)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.05)
        pygame.mixer.music.unload()
        return
    except Exception:
        pass

    # 2. Windows Media Player API via PowerShell (safe parameterized call, no injection risk)
    ps_cmd = (
        'param($p) '
        'Add-Type -AssemblyName PresentationCore; '
        '$m = New-Object System.Windows.Media.MediaPlayer; '
        '$m.Open([System.Uri]$p); '
        'Start-Sleep -Milliseconds 400; '
        '$m.Play(); '
        'Start-Sleep -Seconds 4; '
        '$m.Close()'
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd, "-p", file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


async def synthesize_and_play(text: str, voice: str, pitch: str = "+0Hz", speed: str = "+0%"):
    """Synthesize speech using edge-tts with native rate/pitch parameters and play it."""
    tmp_path = None
    try:
        communicate = edge_tts.Communicate(text, voice=voice, rate=speed, pitch=pitch, volume="+15%")
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = f.name

        await asyncio.wait_for(communicate.save(tmp_path), timeout=8.0)
        play_audio_file(tmp_path)
    except Exception as e:
        print(f"    [Error] Synthesis failed: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def save_to_env(voice_en: str, pitch: str, voice_hi: str = "hi-IN-SwaraNeural"):
    """Update Shin's .env file with the selected voice and pitch."""
    if not ENV_PATH.exists():
        print(f"[!] .env file not found at {ENV_PATH}")
        return

    content = ENV_PATH.read_text(encoding="utf-8")
    content = re.sub(r"^EDGE_TTS_VOICE_EN=.*$", f"EDGE_TTS_VOICE_EN={voice_en}", content, flags=re.MULTILINE)
    content = re.sub(r"^EDGE_TTS_VOICE=.*$", f"EDGE_TTS_VOICE={voice_hi}", content, flags=re.MULTILINE)
    content = re.sub(r"^TTS_PITCH=.*$", f"TTS_PITCH={pitch}", content, flags=re.MULTILINE)
    content = re.sub(r"^TTS_BACKEND=.*$", "TTS_BACKEND=edge", content, flags=re.MULTILINE)

    ENV_PATH.write_text(content, encoding="utf-8")
    print(f"\n[OK] Successfully saved to .env:")
    print(f"     EDGE_TTS_VOICE_EN = {voice_en}")
    print(f"     EDGE_TTS_VOICE    = {voice_hi}")
    print(f"     TTS_PITCH         = {pitch}")
    print(f"     TTS_BACKEND       = edge")


def run_pitch_ladder(voice: str, phrase: str):
    """Play the same phrase at multiple pitch levels to easily compare."""
    pitch_options = [
        ("-6Hz", "Slightly Deep / Chill (-6Hz)"),
        ("+0Hz", "Original Base Pitch (+0Hz)"),
        ("+4Hz", "Natural Cool Girl (+4Hz)"),
        ("+8Hz", "Crisp & Confident (+8Hz)"),
        ("+12Hz", "Youthful & Bright (+12Hz)"),
        ("+16Hz", "Energetic High (+16Hz)"),
    ]

    print(f"\nAuditioning Voice: {voice}")
    print("=" * 60)
    for idx, (p, label) in enumerate(pitch_options, 1):
        print(f" [{idx}] Playing: {label} ...")
        asyncio.run(synthesize_and_play(phrase, voice=voice, pitch=p))
        time.sleep(0.3)

    choice = input("\nEnter the number (1-6) of the pitch you like best (or press Enter to skip): ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(pitch_options):
        selected_pitch = pitch_options[int(choice) - 1][0]
        confirm = input(f"Save {voice} with pitch {selected_pitch} to Shin's .env? (y/n): ").strip().lower()
        if confirm == 'y':
            save_to_env(voice, selected_pitch)


def main():
    print("\n" + "=" * 65)
    print("  Shin Voice & Pitch Tuning Studio — Indian Voices Edition")
    print("=" * 65)
    print(" 1. Audition: hi-IN-SwaraNeural   (Authentic Indian Hindi — Female)")
    print(" 2. Audition: en-IN-NeerjaNeural  (Indian Hinglish/English — Female)")
    print(" 3. Audition: hi-IN-MadhurNeural  (Authentic Indian Hindi — Male)")
    print(" 4. Audition: en-IN-PrabhatNeural (Indian Hinglish/English — Male)")
    print(" 5. Audition: mr-IN-AarohiNeural  (Marathi — Female)")
    print(" 6. Custom Voice / Pitch Audition")
    print(" 7. Exit")
    print("=" * 65)

    while True:
        try:
            choice = input("\nSelect an option (1-7): ").strip()
            if choice == "1":
                run_pitch_ladder("hi-IN-SwaraNeural", SAMPLE_HINGLISH)
            elif choice == "2":
                run_pitch_ladder("en-IN-NeerjaNeural", SAMPLE_HINGLISH)
            elif choice == "3":
                run_pitch_ladder("hi-IN-MadhurNeural", SAMPLE_HINGLISH)
            elif choice == "4":
                run_pitch_ladder("en-IN-PrabhatNeural", SAMPLE_HINGLISH)
            elif choice == "5":
                run_pitch_ladder("mr-IN-AarohiNeural", "नमस्कार, मी शिण आहे. तुम्ही कसे आहात?")
            elif choice == "6":
                v = input("Voice name [default: hi-IN-SwaraNeural]: ").strip() or "hi-IN-SwaraNeural"
                p = input("Pitch (e.g. +4Hz, +8Hz, -4Hz): ").strip() or "+0Hz"
                txt = input("Sample text (press Enter for default): ").strip() or SAMPLE_HINGLISH
                print(f"Playing '{v}' with pitch '{p}'...")
                asyncio.run(synthesize_and_play(txt, voice=v, pitch=p))
                save = input("Save this configuration to .env? (y/n): ").strip().lower()
                if save == 'y':
                    save_to_env(v, p)
            elif choice == "7":
                print("Exiting.")
                break
            else:
                print("Invalid choice, please enter 1 to 7.")
        except KeyboardInterrupt:
            print("\nExiting.")
            break


if __name__ == "__main__":
    main()
