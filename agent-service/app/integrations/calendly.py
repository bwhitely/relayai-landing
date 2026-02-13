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
