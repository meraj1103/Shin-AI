"""
calendar_ai.py — Google Calendar API integration for Shin Voice Assistant
========================================================================
Handles fetching upcoming events and scheduling new ones.
Falls back to a demo/mock mode if credentials.json is not found.
"""

from __future__ import annotations

import os.path
import datetime
import logging
import re
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Scopes required to read and write calendar events
_SCOPES = ['https://www.googleapis.com/auth/calendar']


def _get_credentials():
    """Gets Google Calendar API credentials using local token or oauth flow."""
    # Check if credentials.json exists
    if not os.path.exists('credentials.json'):
        logger.debug("credentials.json not found — Google Calendar API unavailable.")
        return None

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first time.
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', _SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', _SCOPES)
                # Run local server to authenticate
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        return creds
    except Exception as exc:
        logger.warning("Failed to obtain Google Calendar credentials: %s", exc)
        return None


def get_upcoming_events(max_results: int = 5, day: Optional[str] = None) -> List[Dict[str, Any]] | str:
    """
    Fetch upcoming events from the user's Google Calendar.
    If day == 'tomorrow', only returns tomorrow's events.
    Returns a list of event dictionaries, or a descriptive error string.
    """
    creds = _get_credentials()
    if not creds:
        # Fallback to demo calendar mode
        return _get_demo_events(day)

    try:
        from googleapiclient.discovery import build

        service = build('calendar', 'v3', credentials=creds)

        # Time range setup
        now = datetime.datetime.utcnow()
        time_min = now.isoformat() + 'Z'  # 'Z' indicates UTC time
        
        time_max = None
        if day == 'tomorrow':
            tomorrow_start = datetime.datetime.combine(
                datetime.date.today() + datetime.timedelta(days=1),
                datetime.time.min
            )
            tomorrow_end = datetime.datetime.combine(
                datetime.date.today() + datetime.timedelta(days=1),
                datetime.time.max
            )
            time_min = tomorrow_start.isoformat() + 'Z'
            time_max = tomorrow_end.isoformat() + 'Z'
        elif day == 'today':
            today_end = datetime.datetime.combine(
                datetime.date.today(),
                datetime.time.max
            )
            time_max = today_end.isoformat() + 'Z'

        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        return events

    except Exception as exc:
        logger.warning("Failed to query Google Calendar API: %s", exc)
        return f"I had trouble connecting to your calendar. Error details: {exc}"


def create_event(summary: str, start_time_str: str, duration_minutes: int = 30) -> str:
    """
    Schedule a new event on Google Calendar.
    `start_time_str` should be parseable or standard date/time text.
    """
    creds = _get_credentials()
    if not creds:
        return (
            f"Calendar credentials.json was not found, so I couldn't schedule the event '{summary}'. "
            "Please configure the Google Calendar API credentials file to enable this."
        )

    try:
        from googleapiclient.discovery import build
        service = build('calendar', 'v3', credentials=creds)

        # Parse start time
        start_time = _parse_date_time_string(start_time_str)
        end_time = start_time + datetime.timedelta(minutes=duration_minutes)

        # Attach local timezone so it schedules accurately in the user's local time
        local_tz = datetime.datetime.now().astimezone().tzinfo
        start_time = start_time.replace(tzinfo=local_tz)
        end_time = end_time.replace(tzinfo=local_tz)

        event = {
            'summary': summary,
            'start': {
                'dateTime': start_time.isoformat(),
            },
            'end': {
                'dateTime': end_time.isoformat(),
            },
        }

        event = service.events().insert(calendarId='primary', body=event).execute()
        return f"Event '{summary}' successfully created for {start_time.strftime('%A at %I:%M %p')}."

    except Exception as exc:
        logger.warning("Failed to insert Google Calendar event: %s", exc)
        return f"Failed to schedule event. Error: {exc}"


_logged_demo_notice = False

def _get_demo_events(day: Optional[str]) -> List[Dict[str, Any]]:
    """Generates mock/demo events for when credentials.json is not present."""
    global _logged_demo_notice
    if not _logged_demo_notice:
        logger.info("Calendar running in demo mode (no credentials.json).")
        _logged_demo_notice = True
    else:
        logger.debug("Calendar running in demo mode (no credentials.json).")
    
    events = []
    today = datetime.date.today()
    
    # Add fake meetings
    if day == 'tomorrow' or day is None:
        tomorrow = today + datetime.timedelta(days=1)
        events.append({
            'summary': 'Sync with Design Team',
            'start': {
                'dateTime': datetime.datetime.combine(tomorrow, datetime.time(10, 0)).isoformat()
            }
        })
        events.append({
            'summary': 'Weekly Standup',
            'start': {
                'dateTime': datetime.datetime.combine(tomorrow, datetime.time(14, 30)).isoformat()
            }
        })
    
    if day == 'today' or day is None:
        events.append({
            'summary': 'Project Review',
            'start': {
                'dateTime': datetime.datetime.combine(today, datetime.time(16, 0)).isoformat()
            }
        })
        
    return events


def _parse_date_time_string(time_str: str) -> datetime.datetime:
    """Attempts to parse start_time_str into a datetime. Falls back to 1 hour from now."""
    now = datetime.datetime.now()
    
    try:
        # Check standard formats (e.g. 2026-06-16T14:00:00)
        return datetime.datetime.fromisoformat(time_str)
    except ValueError:
        pass

    # Quick relative heuristic: "tomorrow at 3 pm", "friday at 2 pm", "at 5 pm"
    time_str = time_str.lower().strip()
    target_date = now.date()
    target_time = datetime.time((now.hour + 1) % 24, 0) # default to next hour

    # 1. Parse hour/minute
    # Match "at 3:30", "at 3", "at 14"
    time_match = re.search(r'(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(pm|am)?', time_str)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2)) if time_match.group(2) else 0
        ampm = time_match.group(3)
        
        if ampm == 'pm' and hour < 12:
            hour += 12
        elif ampm == 'am' and hour == 12:
            hour = 0
            
        target_time = datetime.time(hour, minute)

    # 2. Parse day
    if "tomorrow" in time_str:
        target_date = now.date() + datetime.timedelta(days=1)
    elif "today" in time_str:
        target_date = now.date()
    else:
        # Match weekday names
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for i, day_name in enumerate(weekdays):
            if re.search(r'\b' + day_name + r'\b', time_str):
                days_ahead = i - now.weekday()
                if days_ahead <= 0: # Target day already happened this week
                    days_ahead += 7
                target_date = now.date() + datetime.timedelta(days=days_ahead)
                break

    return datetime.datetime.combine(target_date, target_time)
