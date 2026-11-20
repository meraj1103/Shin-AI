"""
smart_home.py — IoT Smart Home Control for Shin Voice Assistant
================================================================
Controls Wi-Fi smart devices via the Tuya local API (using tinytuya).
Falls back to a simulated demo mode if no hardware keys are configured.
"""

from __future__ import annotations

import os
import logging
import webbrowser
from typing import Optional

logger = logging.getLogger(__name__)


def _get_tuya_bulb():
    """Initialise local Tuya smart bulb client if credentials exist in .env."""
    dev_id = os.getenv("TUYA_DEVICE_ID", "").strip()
    ip_addr = os.getenv("TUYA_IP", "").strip()
    loc_key = os.getenv("TUYA_LOCAL_KEY", "").strip()

    if not dev_id or not ip_addr or not loc_key:
        logger.debug("Tuya IoT variables missing in .env — Smart Home API running in simulated mode.")
        return None

    try:
        import tinytuya
        # Tuya Bulb (Device Type: Bulb/Light)
        d = tinytuya.BulbDevice(dev_id, ip_addr, loc_key)
        d.set_version(3.3)
        return d
    except Exception as exc:
        logger.warning("Failed to initialize Tuya Bulb client: %s", exc)
        return None


def control_device(state: str, color: Optional[str] = None, brightness: Optional[int] = None) -> str:
    """
    Control a smart home bulb: turn on/off, set color, or set brightness (1-100).
    """
    state = state.lower().strip()
    d = _get_tuya_bulb()
    
    if not d:
        # Simulated demo fallback
        msg = f"[IoT Simulation] Turning smart bulb {state}."
        if color:
            msg += f" Setting color to {color}."
        if brightness:
            msg += f" Setting brightness to {brightness}%."
        logger.info(msg)
        return f"Done. Simulated smart home command: {state}."

    try:
        if state == "off":
            d.turn_off()
            return "Smart lights turned off."
        
        # Ensure device is on for other commands
        d.turn_on()
        
        if color:
            color = color.lower().strip()
            # Map common colors to RGB values
            color_map = {
                "red": (255, 0, 0),
                "green": (0, 255, 0),
                "blue": (0, 0, 255),
                "white": (255, 255, 255),
                "warm": (255, 200, 100),
                "purple": (128, 0, 128),
                "yellow": (255, 255, 0),
                "cyan": (0, 255, 255),
                "orange": (255, 165, 0),
            }
            rgb = color_map.get(color, (255, 255, 255))
            d.set_colour(rgb[0], rgb[1], rgb[2])
            
        if brightness is not None:
            # Scale 1-100 percentage
            brightness = max(1, min(100, brightness))
            d.set_brightness_percentage(brightness)

        return "Smart lights adjusted."

    except Exception as exc:
        logger.warning("Tuya command failed: %s", exc)
        return f"Failed to control smart home device. Error: {exc}"


def activate_scene(scene_name: str) -> str:
    """
    Activate a smart home macro/scene.
    E.g. "movie mode" dims the lights and opens Netflix in a browser.
    """
    scene_name = scene_name.lower().strip()

    if "movie" in scene_name:
        # 1. Dim lights to low blue
        control_device(state="on", color="blue", brightness=10)
        
        # 2. Minimize all windows for focused watching (simulated via hotkey)
        import pyautogui
        pyautogui.hotkey('win', 'd')
        
        # 3. Open Netflix in browser
        webbrowser.open("https://www.netflix.com")
        
        return "Movie mode activated. Lights dimmed to low blue, desktop cleared, opening Netflix."

    elif "work" in scene_name or "focus" in scene_name:
        control_device(state="on", color="white", brightness=100)
        return "Work mode activated. Lights set to bright white for focus."

    elif "sleep" in scene_name or "night" in scene_name:
        control_device(state="off")
        return "Night mode activated. Turning off all lights. Goodnight!"

    return f"Simulated scene '{scene_name}' activated."


def get_device_status() -> str:
    """Query and return the current state of the smart home device."""
    d = _get_tuya_bulb()
    if not d:
        return (
            "Smart home device is running in simulation mode. "
            "Add TUYA_DEVICE_ID, TUYA_IP, and TUYA_LOCAL_KEY to your .env to connect real hardware."
        )
    try:
        status = d.status()
        dps = status.get("dps", {})
        is_on = dps.get("1", False)
        brightness = dps.get("3", None)
        color = dps.get("5", None)

        state_str = "on" if is_on else "off"
        msg = f"The smart lights are currently {state_str}."

        if is_on and brightness is not None:
            # Tuya brightness is typically 25-255 range
            pct = round((brightness - 25) / (255 - 25) * 100)
            msg += f" Brightness is at {pct}%."

        return msg
    except Exception as exc:
        logger.warning("Failed to read device status: %s", exc)
        return "I couldn't read the smart device status right now."
