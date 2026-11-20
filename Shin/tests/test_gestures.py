"""
tests/test_gestures.py — Unit tests for hand landmark gesture classification
"""

import sys
import os
from collections import namedtuple

_project_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(_project_root, "core"))
sys.path.insert(0, _project_root)

import pytest
from gestures import classify_hand_landmarks

Point = namedtuple("Point", ["x", "y", "z"])


def create_mock_landmarks(
    index_ext=False, middle_ext=False, ring_ext=False, pinky_ext=False,
    thumb_up=False, thumb_down=False, thumb_index_touch=False
):
    """Generate 21 mock hand landmarks corresponding to desired finger states."""
    landmarks = [Point(0.5, 0.8, 0.0) for _ in range(21)]

    # Wrist
    landmarks[0] = Point(0.5, 0.8, 0.0)

    # Index finger
    landmarks[6] = Point(0.5, 0.5, 0.0)  # PIP
    landmarks[8] = Point(0.5, 0.3 if index_ext else 0.6, 0.0)  # Tip

    # Middle finger
    landmarks[10] = Point(0.55, 0.5, 0.0)
    landmarks[12] = Point(0.55, 0.3 if middle_ext else 0.6, 0.0)

    # Ring finger
    landmarks[14] = Point(0.6, 0.5, 0.0)
    landmarks[16] = Point(0.6, 0.3 if ring_ext else 0.6, 0.0)

    # Pinky finger
    landmarks[18] = Point(0.65, 0.5, 0.0)
    landmarks[20] = Point(0.65, 0.3 if pinky_ext else 0.6, 0.0)

    # Thumb
    landmarks[2] = Point(0.4, 0.7, 0.0)  # MCP
    if thumb_up:
        landmarks[4] = Point(0.4, 0.2, 0.0)  # Tip up
    elif thumb_down:
        landmarks[4] = Point(0.4, 0.95, 0.0)  # Tip down
    elif thumb_index_touch:
        # Touch index tip (0.5, 0.3)
        landmarks[4] = Point(0.5, 0.3, 0.0)
    else:
        landmarks[4] = Point(0.4, 0.75, 0.0)

    return landmarks


def test_open_palm():
    lm = create_mock_landmarks(index_ext=True, middle_ext=True, ring_ext=True, pinky_ext=True)
    assert classify_hand_landmarks(lm) == "OPEN_PALM"


def test_fist():
    lm = create_mock_landmarks(index_ext=False, middle_ext=False, ring_ext=False, pinky_ext=False)
    assert classify_hand_landmarks(lm) == "FIST"


def test_thumbs_up():
    lm = create_mock_landmarks(index_ext=False, middle_ext=False, ring_ext=False, pinky_ext=False, thumb_up=True)
    assert classify_hand_landmarks(lm) == "THUMBS_UP"


def test_thumbs_down():
    lm = create_mock_landmarks(index_ext=False, middle_ext=False, ring_ext=False, pinky_ext=False, thumb_down=True)
    assert classify_hand_landmarks(lm) == "THUMBS_DOWN"


def test_peace_sign():
    lm = create_mock_landmarks(index_ext=True, middle_ext=True, ring_ext=False, pinky_ext=False)
    assert classify_hand_landmarks(lm) == "PEACE"


def test_point_up():
    lm = create_mock_landmarks(index_ext=True, middle_ext=False, ring_ext=False, pinky_ext=False)
    assert classify_hand_landmarks(lm) == "POINT_UP"


def test_ok_sign():
    lm = create_mock_landmarks(index_ext=True, middle_ext=True, ring_ext=True, pinky_ext=True, thumb_index_touch=True)
    assert classify_hand_landmarks(lm) == "OK_SIGN"
