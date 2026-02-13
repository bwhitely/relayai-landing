import logging

import httpx

logger = logging.getLogger(__name__)

HUBSPOT_API_BASE = "https://api.hubapi.com"


def _headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


async def create_contact(properties: dict, api_key: str) -> dict:
    """Create a contact in HubSpot.

    properties should contain keys like:
        firstname, lastname, email, phone, company, etc.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{HUBSPOT_API_BASE}/crm/v3/objects/contacts",
            headers=_headers(api_key),
            json={"properties": properties},
        )
        if response.status_code == 409:
            # Contact already exists — extract existing ID from error
            detail = response.json()
            return {
                "status": "already_exists",
                "detail": detail.get("message", "Contact already exists"),
            }
        response.raise_for_status()
        data = response.json()
        logger.info("Created HubSpot contact id=%s", data.get("id"))
        return {
            "status": "created",
            "contact_id": data["id"],
            "properties": data.get("properties", {}),
        }


async def update_contact(contact_id: str, properties: dict, api_key: str) -> dict:
    """Update an existing contact in HubSpot.

    contact_id: the HubSpot contact ID.
    properties: dict of fields to update (firstname, lastname, email, phone, etc.)
    """
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.patch(
            f"{HUBSPOT_API_BASE}/crm/v3/objects/contacts/{contact_id}",
            headers=_headers(api_key),
            json={"properties": properties},
        )
        response.raise_for_status()
        data = response.json()
        logger.info("Updated HubSpot contact id=%s", contact_id)
        return {
            "status": "updated",
            "contact_id": data["id"],
            "properties": data.get("properties", {}),
        }


async def search_contacts(query: str, api_key: str) -> list[dict]:
    """Search HubSpot contacts by phone number or email.

    Returns a list of matching contacts with basic properties.
    """
    # Determine if query looks like a phone number or email
    filter_groups = []
    if "@" in query:
        filter_groups.append({
            "filters": [{"propertyName": "email", "operator": "EQ", "value": query}]
        })
    else:
        # Treat as phone number
        filter_groups.append({
            "filters": [{"propertyName": "phone", "operator": "EQ", "value": query}]
        })

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{HUBSPOT_API_BASE}/crm/v3/objects/contacts/search",
            headers=_headers(api_key),
            json={
                "filterGroups": filter_groups,
                "properties": [
                    "firstname", "lastname", "email", "phone", "company",
                ],
                "limit": 10,
            },
        )
        response.raise_for_status()
        data = response.json()
        return [
            {
                "contact_id": result["id"],
                "properties": result.get("properties", {}),
            }
            for result in data.get("results", [])
        ]
