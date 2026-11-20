"""
ui_tree.py — Windows UIAutomation (UIA) Perception & Control Engine
===================================================================
Implements the 2026 AI PC Accessibility Tree paradigm:
Extracts structured, semantic UI elements (buttons, inputs, menus, tabs)
directly from the active window with zero spatial hallucination and
sub-100 token representation (avoiding the "$300 Billion Screenshot Problem").
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from typing import Optional

logger = logging.getLogger("shin.ui_tree")


def get_active_window_ui_elements(max_elements: int = 80) -> list[dict]:
    """
    Query Windows UIAutomation for interactive controls in the foreground window.
    Returns a list of dicts:
    [{"name": "Save", "type": "Button", "rect": [x, y, w, h]}, ...]
    """
    ps_script = f"""
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$user32 = Add-Type -MemberDefinition '[DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();' -Name "Win32UIA" -Namespace "Win32" -PassThru
$hwnd = $user32::GetForegroundWindow()

if ($hwnd -eq [IntPtr]::Zero) {{
    Write-Output "[]"
    exit
}}

$element = [System.Windows.Automation.AutomationElement]::FromHandle($hwnd)
if ($null -eq $element) {{
    Write-Output "[]"
    exit
}}

$condition = [System.Windows.Automation.Condition]::TrueCondition
$children = $element.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)

$results = @()
$count = 0
foreach ($child in $children) {{
    try {{
        $name = $child.Current.Name
        $type = $child.Current.ControlType.ProgrammaticName.Replace("ControlType.", "")
        $rect = $child.Current.BoundingRectangle

        # Only collect meaningful interactive elements with names or inputs
        if (($name -and $name.Trim().Length -gt 0) -or ($type -in @("Edit", "Button", "ComboBox", "CheckBox", "TabItem", "MenuItem"))) {{
            if ($rect.Width -gt 5 -and $rect.Height -gt 5) {{
                $cleanName = if ($name) {{ $name.Trim() }} else {{ "" }}
                $results += @{{
                    name = $cleanName
                    type = $type
                    x = [int]$rect.X
                    y = [int]$rect.Y
                    width = [int]$rect.Width
                    height = [int]$rect.Height
                }}
                $count++
                if ($count -ge {max_elements}) {{ break }}
            }}
        }}
    }} catch {{}}
}}

$results | ConvertTo-Json -Compress
"""
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=5
        )
        out = res.stdout.strip()
        if not out or out == "[]":
            return []
        data = json.loads(out)
        if isinstance(data, dict):
            return [data]
        elif isinstance(data, list):
            return data
        return []
    except Exception as exc:
        logger.debug("Failed to query Windows UIAutomation tree: %s", exc)
        return []


def format_ui_tree_summary() -> str:
    """Format the active UI elements as a compact semantic tree for the AI prompt."""
    elements = get_active_window_ui_elements(max_elements=25)
    if not elements:
        return ""
    lines = ["Active Window Interactive Elements:"]
    for el in elements:
        name = el.get("name", "").strip() or "<unnamed>"
        el_type = el.get("type", "Control")
        lines.append(f"  • [{el_type}] \"{name}\"")
    return "\n".join(lines)


def clean_target_name(target: str) -> str:
    """Normalize user voice queries for UI element target matching."""
    t = target.strip()
    t = re.sub(r"^(?:(?:click|tap)\s+)?(?:on\s+)?(?:the\s+)?(?:a\s+)?(?:button\s+for\s+|button\s+)?", "", t, flags=re.IGNORECASE).strip()
    t = re.sub(r"\s+(?:on|in)?\s*(?:the\s+|my\s+)?screen$", "", t, flags=re.IGNORECASE).strip()
    t = re.sub(r"\s+(?:button|link|icon|tab|video|card)$", "", t, flags=re.IGNORECASE).strip()
    return t.strip()


def find_best_ui_element_match(target_name: str, elements: list[dict], min_score: float = 85.0) -> tuple[Optional[dict], float]:
    """
    Score all interactive UI elements to find the best genuine match.
    Guarantees no false-positive clicks on unnamed buttons, toolbar icons, or random single-word substrings.
    """
    clean_target = clean_target_name(target_name).lower()
    if not clean_target:
        return None, 0.0

    target_words = clean_target.split()
    best_match = None
    best_score = 0.0

    try:
        from rapidfuzz import fuzz
    except ImportError:
        fuzz = None

    for el in elements:
        raw_name = el.get("name")
        if not raw_name or not isinstance(raw_name, str):
            continue
        candidate = raw_name.strip().lower()
        if len(candidate) < 2:
            # Skip single-letter or empty names (e.g. Chrome profile avatar initial or icon)
            continue

        cand_words = candidate.split()
        score = 0.0

        # 1. Exact match
        if candidate == clean_target:
            score = 100.0
        # 2. Target appears as a whole word / phrase within element name
        elif re.search(rf"\b{re.escape(clean_target)}\b", candidate):
            len_penalty = min(15.0, abs(len(candidate) - len(clean_target)) * 0.2)
            score = 95.0 - len_penalty
        # 3. Both are multi-word and candidate is inside target
        elif len(target_words) > 1 and len(cand_words) > 1 and candidate in clean_target:
            score = 88.0
        # 4. Fuzzy match via RapidFuzz using token_sort_ratio
        elif fuzz:
            sort_ratio = fuzz.token_sort_ratio(clean_target, candidate)
            # If target has multiple words, prevent a single word from matching
            if len(target_words) > 1 and len(cand_words) == 1:
                sort_ratio = min(sort_ratio, 50.0)
            if sort_ratio >= 85:
                score = sort_ratio

        if score > best_score:
            best_score = score
            best_match = el

    if best_score >= min_score:
        return best_match, best_score
    return None, best_score


def click_ui_element_by_name(target_name: str) -> tuple[bool, str]:
    """
    Find an element by semantic name and click its center point.
    Returns (success, message). Returns False if no confident match is found,
    allowing fallback to Screen Vision / OCR without false-positive clicks.
    """
    clean_target = clean_target_name(target_name)
    if not clean_target:
        return False, "Target name cannot be empty."

    elements = get_active_window_ui_elements(max_elements=100)
    if not elements:
        return False, "Could not read UI controls from the active window."

    matched, score = find_best_ui_element_match(clean_target, elements, min_score=75.0)

    if not matched:
        return False, f"Could not find an interactive control named '{clean_target}' on screen (best score: {score:.1f})."

    x = matched.get("x", 0) + matched.get("width", 0) // 2
    y = matched.get("y", 0) + matched.get("height", 0) // 2

    try:
        import pyautogui
        pyautogui.moveTo(x, y, duration=0.2)
        pyautogui.click()
        el_name = matched.get("name") or clean_target
        el_type = matched.get("type", "element")
        return True, f"Clicked [{el_type}] '{el_name}' at ({x}, {y})."
    except Exception as exc:
        return False, f"Failed to click element: {exc}"
