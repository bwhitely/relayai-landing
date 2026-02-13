import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_hubspot_create_contact_success():
    from app.integrations.hubspot import create_contact

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "id": "501",
        "properties": {"firstname": "Jane", "lastname": "Doe"},
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.integrations.hubspot.httpx.AsyncClient", return_value=mock_client):
        result = await create_contact(
            {"firstname": "Jane", "lastname": "Doe"},
            "fake-api-key",
        )

    assert result["status"] == "created"
    assert result["contact_id"] == "501"


@pytest.mark.asyncio
async def test_hubspot_create_contact_conflict():
    from app.integrations.hubspot import create_contact

    mock_response = MagicMock()
    mock_response.status_code = 409
    mock_response.json.return_value = {"message": "Contact already exists"}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.integrations.hubspot.httpx.AsyncClient", return_value=mock_client):
        result = await create_contact(
            {"firstname": "Jane"},
            "fake-api-key",
        )

    assert result["status"] == "already_exists"


@pytest.mark.asyncio
async def test_hubspot_search_contacts():
    from app.integrations.hubspot import search_contacts

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {"id": "501", "properties": {"firstname": "Jane", "phone": "+61400000000"}},
        ]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.integrations.hubspot.httpx.AsyncClient", return_value=mock_client):
        results = await search_contacts("+61400000000", "fake-api-key")

    assert len(results) == 1
    assert results[0]["contact_id"] == "501"


@pytest.mark.asyncio
async def test_hubspot_search_by_email():
    """Verify email search uses the email property filter."""
    from app.integrations.hubspot import search_contacts

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"results": []}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.integrations.hubspot.httpx.AsyncClient", return_value=mock_client):
        await search_contacts("jane@example.com", "fake-api-key")

    call_args = mock_client.post.call_args
    body = call_args.kwargs.get("json") or call_args[1].get("json")
    filter_prop = body["filterGroups"][0]["filters"][0]["propertyName"]
    assert filter_prop == "email"


@pytest.mark.asyncio
async def test_hubspot_update_contact():
    from app.integrations.hubspot import update_contact

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "501",
        "properties": {"email": "new@example.com"},
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.patch = AsyncMock(return_value=mock_response)

    with patch("app.integrations.hubspot.httpx.AsyncClient", return_value=mock_client):
        result = await update_contact("501", {"email": "new@example.com"}, "fake-api-key")

    assert result["status"] == "updated"
    assert result["contact_id"] == "501"
    # Verify PATCH was called with the right URL
    call_url = mock_client.patch.call_args.args[0]
    assert "/contacts/501" in call_url
