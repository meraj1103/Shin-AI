"""
gestures.py — Real-time Hand Gesture Recognition for Shin Voice Assistant
===========================================================================
Uses MediaPipe Hands and OpenCV to capture webcam input, detect hand landmarks,
classify natural hand gestures, and execute Windows automation actions.

Supported Gestures:
  🖐️ Open Palm     -> Mute Volume
  ✊ Fist          -> Play / Pause Media
  👍 Thumbs Up     -> Volume Up (+10%)
  👎 Thumbs Down   -> Volume Down (-10%)
  ✌️ Peace / V     -> Take Screenshot
  ☝️ Point Up      -> Scroll Up
  👇 Point Down    -> Scroll Down
  🤟 OK / Rock     -> Next Track
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Global thread state
_gesture_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_is_running = False
_lock = threading.Lock()

# Global callback to execute Shin voice/system commands
_dispatch_cb: Optional[Callable[[str, dict], str]] = None


def init_gestures(dispatch_fn: Callable[[str, dict], str]):
    """Register the command dispatch callback from Shin assistant."""
    global _dispatch_cb
    _dispatch_cb = dispatch_fn


def classify_hand_landmarks(landmarks, handedness_label: str = "Right") -> str:
    """
    Classify 21 3D hand landmarks into a recognised gesture name.
    
    Landmark Indices (MediaPipe):
      0: Wrist
      4: Thumb tip, 3: IP, 2: MCP, 1: CMC
      8: Index tip, 6: Index MCP
      12: Middle tip, 10: Middle MCP
      16: Ring tip, 14: Ring MCP
      20: Pinky tip, 18: Pinky MCP
    """
    try:
        # Extract landmark y coordinates (0 is top of image, 1 is bottom)
        wrist = landmarks[0]
        thumb_tip = landmarks[4]
        thumb_mcp = landmarks[2]

        index_tip = landmarks[8]
        index_pip = landmarks[6]

        middle_tip = landmarks[12]
        middle_pip = landmarks[10]

        ring_tip = landmarks[16]
        ring_pip = landmarks[14]

        pinky_tip = landmarks[20]
        pinky_pip = landmarks[18]

        # Determine if fingers (except thumb) are extended vertically (tip higher/above PIP)
        index_ext = index_tip.y < index_pip.y
        middle_ext = middle_tip.y < middle_pip.y
        ring_ext = ring_tip.y < ring_pip.y
        pinky_ext = pinky_tip.y < pinky_pip.y

        # Determine thumb extension
        # Horizontal thumb distance from MCP
        thumb_is_extended_h = abs(thumb_tip.x - wrist.x) > 0.15
        # Vertical thumb pointing up (tip noticeably above wrist and MCP)
        thumb_pointing_up = thumb_tip.y < thumb_mcp.y - 0.05 and thumb_tip.y < wrist.y - 0.1
        # Vertical thumb pointing down (tip noticeably below wrist and MCP)
        thumb_pointing_down = thumb_tip.y > thumb_mcp.y + 0.05 and thumb_tip.y > wrist.y + 0.1

        # Distance helper
        def dist(p1, p2):
            return ((p1.x - p2.x)**2 + (p1.y - p2.y)**2)**0.5

        # Distance between thumb tip and index tip (for OK sign)
        thumb_index_dist = dist(thumb_tip, index_tip)

        # ── 1. OK Sign / Pinch ──────────────────────────────────────────
        if thumb_index_dist < 0.05 and middle_ext and ring_ext and pinky_ext:
            return "OK_SIGN"

        # ── 2. Thumbs Up ────────────────────────────────────────────────
        if thumb_pointing_up and not index_ext and not middle_ext and not ring_ext and not pinky_ext:
            return "THUMBS_UP"

        # ── 3. Thumbs Down ──────────────────────────────────────────────
        if thumb_pointing_down and not index_ext and not middle_ext and not ring_ext and not pinky_ext:
            return "THUMBS_DOWN"

        # ── 4. Open Palm ────────────────────────────────────────────────
        if index_ext and middle_ext and ring_ext and pinky_ext:
            return "OPEN_PALM"

        # ── 5. Fist ─────────────────────────────────────────────────────
        if not index_ext and not middle_ext and not ring_ext and not pinky_ext and not thumb_pointing_up and not thumb_pointing_down:
            return "FIST"

        # ── 6. Peace / V Sign ───────────────────────────────────────────
        if index_ext and middle_ext and not ring_ext and not pinky_ext:
            return "PEACE"

        # ── 7. Point Up ─────────────────────────────────────────────────
        if index_ext and not middle_ext and not ring_ext and not pinky_ext:
            # Check if index is pointing up
            if index_tip.y < index_pip.y:
                return "POINT_UP"

        # ── 8. Point Down ───────────────────────────────────────────────
        index_pointing_down = index_tip.y > index_pip.y + 0.05
        if index_pointing_down and not middle_ext and not ring_ext and not pinky_ext:
            return "POINT_DOWN"

    except Exception as exc:
        logger.debug("Error in gesture classification: %s", exc)

    return "UNKNOWN"


def _gesture_loop():
    """Background worker loop processing camera frames."""
    global _is_running
    logger.info("Starting Hand Gesture Recognition engine...")

    try:
        import cv2
        import mediapipe as mp
        import pyautogui

        mp_hands = mp.solutions.hands
        hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.65,
            min_tracking_confidence=0.6,
        )

        # Use CAP_DSHOW on Windows for fast webcam initialization
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            # Fallback to default backend
            cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            logger.error("Webcam device could not be opened for hand gestures.")
            _is_running = False
            return

        logger.info("Webcam active. Hand Gesture commands ready!")

        last_gesture = "UNKNOWN"
        consecutive_count = 0
        STABILITY_THRESHOLD = 3  # Must see same gesture in 3 consecutive frames
        last_execution_time = 0.0
        COOLDOWN_DEFAULT = 1.2    # Cooldown seconds between commands
        COOLDOWN_SCROLL = 0.3     # Shorter cooldown for smooth scrolling

        while not _stop_event.is_set():
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.03)
                continue

            # Flip frame horizontally for natural selfie view & RGB conversion
            frame_rgb = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)
            results = hands.process(frame_rgb)

            current_gesture = "UNKNOWN"
            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    current_gesture = classify_hand_landmarks(hand_landmarks.landmark)
                    break

            if current_gesture != "UNKNOWN":
                if current_gesture == last_gesture:
                    consecutive_count += 1
                else:
                    last_gesture = current_gesture
                    consecutive_count = 1

                # Trigger command when gesture is stabilized and cooldown has elapsed
                if consecutive_count >= STABILITY_THRESHOLD:
                    now = time.time()
                    cooldown = COOLDOWN_SCROLL if "POINT" in current_gesture else COOLDOWN_DEFAULT

                    if (now - last_execution_time) >= cooldown:
                        last_execution_time = now
                        logger.info("🖐️ Gesture Triggered: %s", current_gesture)
                        _execute_gesture_action(current_gesture)
            else:
                last_gesture = "UNKNOWN"
                consecutive_count = 0

            time.sleep(0.02)  # ~50 FPS max sampling rate

    except Exception as exc:
        logger.error("Error in gesture recognition loop: %s", exc)
    finally:
        try:
            if 'cap' in locals() and cap.isOpened():
                cap.release()
            if 'hands' in locals():
                hands.close()
        except Exception:
            pass
        _is_running = False
        logger.info("Hand Gesture Recognition engine stopped.")


def _execute_gesture_action(gesture: str):
    """Execute corresponding Shin command or desktop action for detected gesture."""
    import pyautogui
    
    try:
        if gesture == "OPEN_PALM":
            logger.info("Gesture Action: Mute Volume")
            pyautogui.press("volumemute")

        elif gesture == "FIST":
            logger.info("Gesture Action: Play/Pause Media")
            pyautogui.press("playpause")

        elif gesture == "THUMBS_UP":
            logger.info("Gesture Action: Volume Up")
            pyautogui.press("volumeup")

        elif gesture == "THUMBS_DOWN":
            logger.info("Gesture Action: Volume Down")
            pyautogui.press("volumedown")

        elif gesture == "PEACE":
            logger.info("Gesture Action: Screenshot")
            pyautogui.hotkey("win", "prtscr")

        elif gesture == "POINT_UP":
            logger.info("Gesture Action: Scroll Up")
            pyautogui.scroll(300)

        elif gesture == "POINT_DOWN":
            logger.info("Gesture Action: Scroll Down")
            pyautogui.scroll(-300)

        elif gesture == "OK_SIGN":
            logger.info("Gesture Action: Next Track")
            pyautogui.press("nexttrack")

    except Exception as exc:
        logger.error("Failed to execute gesture action %s: %s", gesture, exc)


def start_gesture_control() -> bool:
    """Start hand gesture recognition in a background thread."""
    global _gesture_thread, _is_running
    with _lock:
        if _is_running:
            return True
        _stop_event.clear()
        _is_running = True
        _gesture_thread = threading.Thread(target=_gesture_loop, daemon=True, name="GestureEngine")
        _gesture_thread.start()
        return True


def stop_gesture_control() -> bool:
    """Stop hand gesture recognition thread and release camera."""
    global _is_running, _gesture_thread
    with _lock:
        if not _is_running:
            return True
        _stop_event.set()
        if _gesture_thread and _gesture_thread.is_alive():
            _gesture_thread.join(timeout=2.0)
        _is_running = False
        return True


def is_gesture_active() -> bool:
    """Return True if gesture control is currently running."""
    return _is_running


def toggle_gesture_control() -> bool:
    """Toggle hand gesture recognition state."""
    if is_gesture_active():
        stop_gesture_control()
        return False
    else:
        start_gesture_control()
        return True
