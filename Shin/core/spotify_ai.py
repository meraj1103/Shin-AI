"""
spotify_ai.py — Native Spotify AI Control for Shin Voice Assistant
===================================================================
Uses spotipy to interact with the Spotify Web API.
Falls back to pyautogui-based media keys if credentials are missing or the API fails.
"""

from __future__ import annotations

import os
import logging
from typing import Optional
import pyautogui

logger = logging.getLogger(__name__)


def _get_spotify_client():
    """Build spotipy client using .env credentials. Returns None if missing."""
    client_id = os.getenv("SPOTIPY_CLIENT_ID", "").strip()
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI", "http://localhost:8888/callback").strip()

    if not client_id or not client_secret:
        logger.debug("Spotify credentials missing in .env — Spotify Web API disabled.")
        return None

    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth

        # Scope for control and reading playback status
        scope = "user-modify-playback-state user-read-playback-state user-read-currently-playing"
        
        auth_manager = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=scope,
            open_browser=True
        )
        sp = spotipy.Spotify(auth_manager=auth_manager)
        return sp
    except Exception as exc:
        logger.warning("Failed to initialize Spotify client: %s", exc)
        return None


def play_track_or_playlist(query: str) -> str:
    """
    Search and play a track or playlist on Spotify.
    Falls back to opening Spotify app if Web API is not active.
    """
    sp = _get_spotify_client()
    if not sp:
        # Fallback to local media play shortcut (keyboard key) or web open
        pyautogui.press('playpause')
        return f"Spotify API keys not configured. Attempted play/pause keyboard command."

    try:
        # 1. Try to find active device
        devices = sp.devices()
        device_id = None
        for d in devices.get('devices', []):
            if d.get('is_active'):
                device_id = d.get('id')
                break
        if not device_id and devices.get('devices'):
            device_id = devices['devices'][0]['id']

        # 2. Search for tracks/playlists
        is_playlist = "playlist" in query.lower()
        search_type = 'playlist' if is_playlist else 'track'
        
        results = sp.search(q=query, limit=1, type=search_type)
        items = results.get(search_type + 's', {}).get('items', [])

        if not items:
            return f"I couldn't find any {search_type} matching '{query}' on Spotify."

        item = items[0]
        uri = item.get('uri')
        name = item.get('name')

        # Get album art URL
        art_url = ""
        if not is_playlist:
            images = item.get("album", {}).get("images", [])
            if images:
                art_url = images[0].get("url", "")
        
        # Get artist names
        artists = ", ".join([a.get('name', '') for a in item.get('artists', [])])

        # 3. Play
        if is_playlist:
            sp.start_playback(device_id=device_id, context_uri=uri)
        else:
            sp.start_playback(device_id=device_id, uris=[uri])

        # 4. Update UI now-playing widget
        try:
            from ui_server import UIBridge
            UIBridge.send_now_playing(name, artists, art_url)
        except Exception:
            pass

        return f"Playing '{name}' on Spotify."

    except Exception as exc:
        logger.warning("Spotify play API failed: %s", exc)
        # Attempt to resume via hotkey as fallback
        pyautogui.press('playpause')
        return f"Attempted to play '{query}' on Spotify, but ran into an API issue. Fired global play hotkey instead."


def get_current_track_info() -> str:
    """Return description of currently playing Spotify track."""
    sp = _get_spotify_client()
    if not sp:
        return "Spotify API keys not set. I can't read active track metadata."

    try:
        current = sp.currently_playing()
        if not current or not current.get('is_playing'):
            return "Nothing is currently playing on Spotify."

        item = current.get('item', {})
        if not item:
            return "Nothing is currently playing on Spotify."

        track_name = item.get('name')
        artists = ", ".join([a.get('name') for a in item.get('artists', [])])
        return f"Currently playing '{track_name}' by {artists}."
    except Exception as exc:
        logger.warning("Spotify get track info failed: %s", exc)
        return "I couldn't fetch current track information from Spotify."


def control_playback(action: str) -> str:
    """Control active Spotify playback: play, pause, next, previous."""
    action = action.lower().strip()
    sp = _get_spotify_client()

    if not sp:
        # Fallback to global hardware keys
        if action in ("play", "pause", "play_pause", "resume"):
            pyautogui.press('playpause')
            return "Fired global play-pause hotkey."
        elif action == "next":
            pyautogui.press('nexttrack')
            return "Fired global next-track hotkey."
        elif action in ("previous", "back"):
            pyautogui.press('prevtrack')
            return "Fired global previous-track hotkey."
        return f"Unknown media action: {action}"

    try:
        devices = sp.devices()
        device_id = None
        for d in devices.get('devices', []):
            if d.get('is_active'):
                device_id = d.get('id')
                break

        if action == "play_pause":
            # True toggle: check current state and do the opposite
            current = sp.currently_playing()
            if current and current.get('is_playing'):
                sp.pause_playback(device_id=device_id)
                try:
                    from ui_server import UIBridge
                    UIBridge.send_media_clear()
                except Exception:
                    pass
                return "Playback paused on Spotify."
            else:
                sp.start_playback(device_id=device_id)
                return "Playback resumed on Spotify."

        elif action in ("play", "resume"):
            sp.start_playback(device_id=device_id)
            return "Playback resumed on Spotify."
        elif action == "pause":
            sp.pause_playback(device_id=device_id)
            try:
                from ui_server import UIBridge
                UIBridge.send_media_clear()
            except Exception:
                pass
            return "Playback paused on Spotify."
        elif action == "next":
            sp.next_track(device_id=device_id)
            return "Skipped to the next track on Spotify."
        elif action in ("previous", "back"):
            sp.previous_track(device_id=device_id)
            return "Went back to the previous track on Spotify."

        return f"Spotify action '{action}' completed."
    except Exception as exc:
        logger.warning("Spotify control API failed for %s: %s", action, exc)
        # Fallback to key presses
        if action in ("play", "pause", "resume", "play_pause"):
            pyautogui.press('playpause')
        elif action == "next":
            pyautogui.press('nexttrack')
        elif action in ("previous", "back"):
            pyautogui.press('prevtrack')
        return f"Spotify API control failed. Executed hardware key fallback for {action}."
