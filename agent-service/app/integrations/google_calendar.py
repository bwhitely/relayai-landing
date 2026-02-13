import logging
from datetime import datetime, timedelta, timezone

import httpx
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"


def _get_credentials(creds_dict: dict) -> Credentials:
    """Build service account credentials from stored key fields."""
    info = {
        "type": "service_account",
        "client_email": creds_dict["client_email"],
        "private_key": creds_dict["private_key"],
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    return Credentials.from_service_account_info(info, scopes=SCOPES)


def get_access_token(creds_dict: dict) -> str:
    """Get a short-lived access token from service account credentials."""
    credentials = _get_credentials(creds_dict)
    credentials.refresh(Request())
    return credentials.token


async def check_availability(
    calendar_id: str,
    start: str,
    end: str,
    creds_dict: dict,
) -> list[dict]:
    """Check free/busy slots on a Google Calendar.

    Uses the FreeBusy API to find busy periods, then returns them
    so the agent can identify free windows.

    Args:
        calendar_id: The calendar ID (email or 'primary').
        start: ISO datetime string for range start.
        end: ISO datetime string for range end.
        creds_dict: Dict with client_email, private_key, calendar_id.

    Returns:
        List of busy periods with start/end times.
    """
    token = get_access_token(creds_dict)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = {
        "timeMin": start,
        "timeMax": end,
        "items": [{"id": calendar_id}],
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{CALENDAR_API_BASE}/freeBusy",
            headers=headers,
            json=body,
        )
        response.raise_for_status()
        data = response.json()

    calendar_data = data.get("calendars", {}).get(calendar_id, {})
    busy_periods = calendar_data.get("busy", [])

    return [
        {"start": period["start"], "end": period["end"]}
        for period in busy_periods
    ]


async def list_events(
    calendar_id: str,
    time_min: str,
    time_max: str,
    creds_dict: dict,
) -> list[dict]:
    """List events in a date range on a Google Calendar.

    Args:
        calendar_id: The calendar ID.
        time_min: ISO datetime string for range start.
        time_max: ISO datetime string for range end.
        creds_dict: Dict with client_email, private_key.

    Returns:
        List of events with id, summary, start, end.
    """
    token = get_access_token(creds_dict)
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "timeMin": time_min,
        "timeMax": time_max,
        "singleEvents": "true",
        "orderBy": "startTime",
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{CALENDAR_API_BASE}/calendars/{calendar_id}/events",
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        data = response.json()

    return [
        {
            "id": event["id"],
            "summary": event.get("summary", ""),
            "start": event.get("start", {}).get("dateTime", event.get("start", {}).get("date", "")),
            "end": event.get("end", {}).get("dateTime", event.get("end", {}).get("date", "")),
        }
        for event in data.get("items", [])
    ]


async def create_event(
    calendar_id: str,
    summary: str,
    start: str,
    end: str,
    creds_dict: dict,
    description: str | None = None,
) -> dict:
    """Create an event on a Google Calendar.

    Args:
        calendar_id: The calendar ID.
        summary: Event title.
        start: ISO datetime string for event start.
        end: ISO datetime string for event end.
        creds_dict: Dict with client_email, private_key.
        description: Optional event description.

    Returns:
        Dict with status, event_id, start, end.
    """
    token = get_access_token(creds_dict)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body: dict = {
        "summary": summary,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
    }
    if description:
        body["description"] = description

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{CALENDAR_API_BASE}/calendars/{calendar_id}/events",
            headers=headers,
            json=body,
        )
        response.raise_for_status()
        data = response.json()

    logger.info("Created Google Calendar event id=%s", data.get("id"))
    return {
        "status": "booked",
        "event_id": data["id"],
        "summary": data.get("summary", ""),
        "start": data.get("start", {}).get("dateTime", ""),
        "end": data.get("end", {}).get("dateTime", ""),
        "html_link": data.get("htmlLink", ""),
    }
