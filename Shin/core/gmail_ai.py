"""
gmail_ai.py — Gmail integration for Shin Voice Assistant
=========================================================
Reads latest emails via the Gmail API (read-only scope).

Setup:
  1. Go to https://console.cloud.google.com/
  2. Create a project → Enable Gmail API
  3. Create OAuth 2.0 Desktop credentials → Download as 'gmail_credentials.json'
     and place it in the Shin project root.
  4. On first run, a browser will open for authorization. A token.json is saved
     automatically for subsequent runs.

.env keys (optional overrides):
    GMAIL_MAX_EMAILS     — how many emails to read aloud (default: 5)
    GMAIL_CREDENTIALS    — path to credentials JSON (default: ./gmail_credentials.json)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
_CREDS_FILE = os.getenv("GMAIL_CREDENTIALS", str(Path(__file__).parent.parent / "gmail_credentials.json"))
_TOKEN_FILE = str(Path(__file__).parent.parent / "gmail_token.json")
_MAX_EMAILS = int(os.getenv("GMAIL_MAX_EMAILS", "5"))


def _get_gmail_service():
    """Authenticate and return a Gmail API service object."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        raise ImportError(
            "Google API libraries not installed. "
            "Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )

    if not Path(_CREDS_FILE).exists():
        raise FileNotFoundError(
            f"Gmail credentials not found at '{_CREDS_FILE}'. "
            "Please download OAuth 2.0 credentials from Google Cloud Console."
        )

    creds = None
    if Path(_TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(_TOKEN_FILE, _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(_CREDS_FILE, _SCOPES)
            creds = flow.run_local_server(port=0)
        with open(_TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def _decode_header(encoded: str) -> str:
    """Decode RFC 2047 email header."""
    import email.header
    parts = email.header.decode_header(encoded)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def get_latest_emails(max_results: Optional[int] = None, unread_only: bool = True) -> str:
    """
    Fetch and return a spoken summary of the latest emails.
    """
    count = max_results or _MAX_EMAILS

    try:
        service = _get_gmail_service()
    except ImportError as e:
        return str(e)
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        return f"I couldn't connect to Gmail: {e}"

    try:
        query = "is:unread" if unread_only else ""
        result = service.users().messages().list(
            userId="me",
            maxResults=count,
            q=query,
            labelIds=["INBOX"],
        ).execute()

        messages = result.get("messages", [])
        if not messages:
            label = "unread " if unread_only else ""
            return f"You have no {label}emails in your inbox."

        summaries = []
        for msg_ref in messages[:count]:
            msg = service.users().messages().get(
                userId="me",
                id=msg_ref["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()

            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            subject = _decode_header(headers.get("Subject", "(No Subject)"))
            sender_raw = headers.get("From", "Unknown sender")
            # Extract display name if present e.g. "John Doe <john@example.com>"
            if "<" in sender_raw:
                sender = sender_raw.split("<")[0].strip().strip('"')
            else:
                sender = sender_raw.split("@")[0]

            summaries.append(f"From {sender}: {subject}")

        if len(summaries) == 1:
            return f"You have 1 {'unread ' if unread_only else ''}email. {summaries[0]}."

        intro = f"You have {len(summaries)} {'unread ' if unread_only else ''}emails. "
        listed = ". ".join(summaries) + "."
        return intro + listed

    except Exception as exc:
        logger.exception("Failed to fetch emails")
        return f"I ran into an error reading your emails: {exc}"
