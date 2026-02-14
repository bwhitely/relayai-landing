import logging

import httpx

logger = logging.getLogger(__name__)

CALENDLY_API_BASE = "https://api.calendly.com"


def _headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


async def get_available_times(
    event_type_uri: str,
    start_time: str,
    end_time: str,
    api_key: str,
) -> list[dict]:
    """Get available times for a Calendly event type.

    Args:
        event_type_uri: Full Calendly event type URI
            (e.g. https://api.calendly.com/event_types/UUID).
        start_time: ISO datetime for range start.
        end_time: ISO datetime for range end.
        api_key: Calendly Personal Access Token.

    Returns:
        List of available time slots with start_time and status.
    """
    params = {
        "event_type": event_type_uri,
        "start_time": start_time,
        "end_time": end_time,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{CALENDLY_API_BASE}/event_type_available_times",
            headers=_headers(api_key),
            params=params,
        )
        response.raise_for_status()
        data = response.json()

    return [
        {
            "start_time": slot["start_time"],
            "status": slot.get("status", "available"),
        }
        for slot in data.get("collection", [])
    ]


async def get_scheduling_link(
    event_type_uri: str,
    api_key: str,
) -> dict:
    """Get the public scheduling link for a Calendly event type.

    Args:
        event_type_uri: Full Calendly event type URI.
        api_key: Calendly Personal Access Token.

    Returns:
        Dict with scheduling_url and event type name.
    """
    # Extract UUID from URI
    uuid = event_type_uri.rstrip("/").split("/")[-1]

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{CALENDLY_API_BASE}/event_types/{uuid}",
            headers=_headers(api_key),
        )
        response.raise_for_status()
        data = response.json()

    resource = data.get("resource", {})
    return {
        "scheduling_url": resource.get("scheduling_url", ""),
        "name": resource.get("name", ""),
        "duration_minutes": resource.get("duration", 0),
    }


async def get_user_uri(api_key: str) -> str:
    """Get the current user's URI from Calendly API."""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{CALENDLY_API_BASE}/users/me",
            headers=_headers(api_key),
        )
        response.raise_for_status()
        data = response.json()
    return data.get("resource", {}).get("uri", "")


async def list_scheduled_events(
    api_key: str,
    min_start_time: str | None = None,
    max_start_time: str | None = None,
    invitee_email: str | None = None,
) -> list[dict]:
    """List scheduled events from Calendly.

    Args:
        api_key: Calendly Personal Access Token.
        min_start_time: ISO datetime — only events starting after this.
        max_start_time: ISO datetime — only events starting before this.
        invitee_email: Filter by invitee email address.

    Returns:
        List of scheduled events with uri, name, start, end, status.
    """
    user_uri = await get_user_uri(api_key)
    if not user_uri:
        return []

    params: dict = {
        "user": user_uri,
        "status": "active",
    }
    if min_start_time:
        params["min_start_time"] = min_start_time
    if max_start_time:
        params["max_start_time"] = max_start_time
    if invitee_email:
        params["invitee_email"] = invitee_email

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{CALENDLY_API_BASE}/scheduled_events",
            headers=_headers(api_key),
            params=params,
        )
        response.raise_for_status()
        data = response.json()

    return [
        {
            "event_uri": event["uri"],
            "name": event.get("name", ""),
            "start_time": event.get("start_time", ""),
            "end_time": event.get("end_time", ""),
            "status": event.get("status", ""),
        }
        for event in data.get("collection", [])
    ]


async def cancel_event(
    event_uri: str,
    reason: str,
    api_key: str,
) -> dict:
    """Cancel a scheduled Calendly event.

    Args:
        event_uri: The full event URI from list_scheduled_events.
        reason: Cancellation reason.
        api_key: Calendly Personal Access Token.

    Returns:
        Dict with status and event_uri.
    """
    # Extract UUID from URI
    uuid = event_uri.rstrip("/").split("/")[-1]

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{CALENDLY_API_BASE}/scheduled_events/{uuid}/cancellation",
            headers=_headers(api_key),
            json={"reason": reason},
        )
        response.raise_for_status()

    logger.info("Cancelled Calendly event uuid=%s", uuid)
    return {
        "status": "cancelled",
        "event_uri": event_uri,
    }
