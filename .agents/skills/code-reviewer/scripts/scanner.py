"""
scanner.py — Code Security, Anti-Pattern & Style Scanner
=========================================================
Scans Python (.py) and JavaScript (.js) files for security risks,
anti-patterns, and style violations.
"""

import sys
import os
import re
from pathlib import Path


def scan_file(filepath: str) -> list[dict]:
    """Scan a source file and return a list of findings."""
    path = Path(filepath)
    if not path.exists():
        print(f"Error: File {filepath} not found.")
        return []

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            lines = content.splitlines()
    except Exception as exc:
        print(f"Error reading {filepath}: {exc}")
        return []

    findings = []
    ext = path.suffix.lower()

    print(f"--- Scanning {filepath} ({len(lines)} lines) ---")

    # ══════════════════════════════════════════════════════════════════════════
    # 1. SECURITY CHECKS
    # ══════════════════════════════════════════════════════════════════════════

    # Hardcoded secrets / passwords / tokens
    secret_patterns = [
        (r'(?:password|secret|api_key|token|access_key)\s*=\s*[\'"][^\'"]{6,}[\'"]', "Potential hardcoded credential or secret key"),
        (r'["\'](?:AIza[0-9A-Za-z-_]{35}|ghp_[0-9A-Za-z]{36}|sk-[0-9A-Za-z]{32,})["\']', "Exposed cloud/API secret token token"),
    ]
    for pattern, desc in secret_patterns:
        for idx, line in enumerate(lines, 1):
            if re.search(pattern, line, re.IGNORECASE) and not line.strip().startswith(("#", "//", "/*")):
                findings.append({"type": "SECURITY", "line": idx, "message": f"{desc} on line {idx}."})

    # Insecure code execution
    insecure_exec = [
        (r'\beval\s*\(', "Use of eval() introduces arbitrary code execution vulnerabilities"),
        (r'\bexec\s*\(', "Use of exec() introduces arbitrary code execution vulnerabilities"),
        (r'subprocess\.(?:Popen|run|call)\s*\(.+shell\s*=\s*True', "subprocess call with shell=True is susceptible to command injection"),
    ]
    for pattern, desc in insecure_exec:
        for idx, line in enumerate(lines, 1):
            if re.search(pattern, line) and not line.strip().startswith(("#", "//")):
                findings.append({"type": "SECURITY", "line": idx, "message": f"{desc} on line {idx}."})

    # SQL Injection via string formatting
    sql_patterns = [
        (r'(?:execute|query)\s*\(\s*f["\'].*SELECT|INSERT|UPDATE|DELETE', "SQL query constructed using f-string interpolation (SQL injection risk)"),
        (r'(?:execute|query)\s*\(\s*["\'].*%s.*["\']\s*%', "SQL query constructed with % formatting instead of parameterized arguments"),
    ]
    for pattern, desc in sql_patterns:
        for idx, line in enumerate(lines, 1):
            if re.search(pattern, line, re.IGNORECASE):
                findings.append({"type": "SECURITY", "line": idx, "message": f"{desc} on line {idx}."})

    # ══════════════════════════════════════════════════════════════════════════
    # 2. ANTI-PATTERNS
    # ══════════════════════════════════════════════════════════════════════════

    # Broad exception handling in Python
    if ext == ".py":
        for idx, line in enumerate(lines, 1):
            if re.search(r'^\s*except\s*:\s*$', line):
                findings.append({"type": "ANTI-PATTERN", "line": idx, "message": f"Bare 'except:' clause catches SystemExit and KeyboardInterrupt. Use 'except Exception:'."})
            elif re.search(r'^\s*except\s+Exception\s*:\s*pass\s*$', line):
                findings.append({"type": "ANTI-PATTERN", "line": idx, "message": f"Silent broad exception suppression ('except Exception: pass') hides critical bugs."})

    # JavaScript loose equality and var declarations
    if ext in (".js", ".ts", ".jsx", ".tsx"):
        for idx, line in enumerate(lines, 1):
            if re.search(r'\bvar\s+[a-zA-Z0-9_]+', line) and not line.strip().startswith(("//", "/*")):
                findings.append({"type": "ANTI-PATTERN", "line": idx, "message": f"Use of 'var' on line {idx}. Prefer block-scoped 'const' or 'let'."})
            if re.search(r'[^!=]==[^=]', line) and not line.strip().startswith(("//", "/*")):
                findings.append({"type": "ANTI-PATTERN", "line": idx, "message": f"Loose equality (==) on line {idx}. Prefer strict equality (===)."})

    # Resource leaks (open without with)
    if ext == ".py":
        for idx, line in enumerate(lines, 1):
            if re.search(r'^\s*[a-zA-Z0-9_]+\s*=\s*open\s*\(', line) and "with open" not in line:
                findings.append({"type": "ANTI-PATTERN", "line": idx, "message": f"File opened without 'with' context manager on line {idx}. Risk of resource leak."})

    # ══════════════════════════════════════════════════════════════════════════
    # 3. STYLE SUGGESTIONS
    # ══════════════════════════════════════════════════════════════════════════

    # Missing docstrings for functions in Python
    if ext == ".py":
        for idx, line in enumerate(lines, 1):
            if re.match(r'^\s*def\s+[a-zA-Z0-9_]+\s*\(', line) and not line.strip().startswith("def _"):
                # Check next 2 lines for docstring
                next_block = "\n".join(lines[idx:idx+3])
                if '"""' not in next_block and "'''" not in next_block:
                    findings.append({"type": "STYLE", "line": idx, "message": f"Public function on line {idx} appears to be missing a docstring."})

    # Line length > 120
    for idx, line in enumerate(lines, 1):
        if len(line) > 120 and not line.strip().startswith(("#", "//", "http")):
            findings.append({"type": "STYLE", "line": idx, "message": f"Line {idx} exceeds 120 characters ({len(line)} chars). Consider breaking it."})

    # Output findings
    for item in findings:
        print(f"[{item['type']}] Line {item['line']}: {item['message']}")

    if not findings:
        print("No critical security or style issues found. Clean scan!")

    print("Scan complete.")
    return findings


if __name__ == "__main__":
    if len(sys.argv) > 1:
        scan_file(sys.argv[1])
    else:
        print("Usage: python scanner.py <file_path>")
