import json
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.tools import execute_tool
from app.models.tenant import CRMType, Tenant


@pytest.fixture
def hubspot_tenant() -> Tenant:
    return Tenant(
        name="HubSpot Business",
        crm_type=CRMType.hubspot,
        crm_credentials="encrypted-hubspot-key",
        is_active=True,
        max_conversations_per_month=100,
    )


@pytest.fixture
def sheets_tenant() -> Tenant:
    return Tenant(
        name="Sheets Business",
        crm_type=CRMType.google_sheets,
        crm_credentials="encrypted-sheets-creds",
        is_active=True,
        max_conversations_per_month=100,
    )


@pytest.fixture
def no_crm_tenant() -> Tenant:
    return Tenant(
        name="No CRM Business",
        crm_type=CRMType.none,
        is_active=True,
        max_conversations_per_month=100,
    )


@pytest.mark.asyncio
async def test_create_lead_hubspot(hubspot_tenant):
    """create_lead dispatches to HubSpot when tenant uses HubSpot CRM."""
    mock_create = AsyncMock(return_value={
        "status": "created",
        "contact_id": "123",
        "properties": {"firstname": "Jane"},
    })

    with (
        patch("app.agent.tools._get_crm_credentials", return_value="fake-api-key"),
        patch("app.agent.tools._create_lead_handler.__module__", create=True),
        patch("app.integrations.hubspot.create_contact", mock_create),
    ):
        # Need to patch at the import site inside the handler
        with patch("app.integrations.hubspot.create_contact", mock_create):
            result = json.loads(await execute_tool(
                "create_lead",
                {"first_name": "Jane", "last_name": "Doe", "email": "jane@example.com"},
                hubspot_tenant,
            ))

    assert result["status"] == "created"
    assert result["contact_id"] == "123"


@pytest.mark.asyncio
async def test_create_lead_google_sheets(sheets_tenant):
    """create_lead dispatches to Google Sheets when tenant uses Sheets CRM."""
    mock_append = AsyncMock(return_value={
        "status": "appended",
        "updated_range": "Sheet1!A2:F2",
        "updated_rows": 1,
    })
    creds_json = json.dumps({
        "sheet_id": "abc123",
        "client_email": "test@test.iam.gserviceaccount.com",
        "private_key": "fake",
    })

    with (
        patch("app.agent.tools._get_crm_credentials", return_value=creds_json),
        patch("app.integrations.google_sheets.append_row", mock_append),
    ):
        result = json.loads(await execute_tool(
            "create_lead",
            {"first_name": "Jane", "phone": "+61400000000"},
            sheets_tenant,
        ))

    assert result["status"] == "appended"
    mock_append.assert_called_once()


@pytest.mark.asyncio
async def test_create_lead_no_crm(no_crm_tenant):
    """create_lead returns error when tenant has no CRM configured."""
    result = json.loads(await execute_tool(
        "create_lead",
        {"first_name": "Jane"},
        no_crm_tenant,
    ))
    assert "error" in result


@pytest.mark.asyncio
async def test_search_contacts_hubspot(hubspot_tenant):
    """search_contacts dispatches to HubSpot search."""
    mock_search = AsyncMock(return_value=[
        {"contact_id": "456", "properties": {"firstname": "John", "phone": "+61400000000"}},
    ])

    with (
        patch("app.agent.tools._get_crm_credentials", return_value="fake-api-key"),
        patch("app.integrations.hubspot.search_contacts", mock_search),
    ):
        result = json.loads(await execute_tool(
            "search_contacts",
            {"query": "+61400000000"},
            hubspot_tenant,
        ))

    assert result["count"] == 1
    assert result["results"][0]["contact_id"] == "456"


@pytest.mark.asyncio
async def test_search_contacts_google_sheets(sheets_tenant):
    """search_contacts searches rows in Google Sheets."""
    mock_read = AsyncMock(return_value=[
        ["Jane", "Doe", "jane@example.com", "+61400000000"],
        ["John", "Smith", "john@example.com", "+61411111111"],
    ])
    creds_json = json.dumps({
        "sheet_id": "abc123",
        "client_email": "test@test.iam.gserviceaccount.com",
        "private_key": "fake",
    })

    with (
        patch("app.agent.tools._get_crm_credentials", return_value=creds_json),
        patch("app.integrations.google_sheets.read_rows", mock_read),
    ):
        result = json.loads(await execute_tool(
            "search_contacts",
            {"query": "jane"},
            sheets_tenant,
        ))

    assert result["count"] == 1
    assert "Jane" in result["results"][0]


@pytest.mark.asyncio
async def test_search_contacts_empty_query(hubspot_tenant):
    """search_contacts returns error for empty query."""
    result = json.loads(await execute_tool(
        "search_contacts",
        {"query": ""},
        hubspot_tenant,
    ))
    assert "error" in result


# --- update_lead tests ---

@pytest.mark.asyncio
async def test_update_lead_hubspot(hubspot_tenant):
    """update_lead dispatches to HubSpot update_contact."""
    mock_update = AsyncMock(return_value={
        "status": "updated",
        "contact_id": "456",
        "properties": {"email": "new@example.com"},
    })

    with (
        patch("app.agent.tools._get_crm_credentials", return_value="fake-api-key"),
        patch("app.integrations.hubspot.update_contact", mock_update),
    ):
        result = json.loads(await execute_tool(
            "update_lead",
            {"contact_id": "456", "email": "new@example.com"},
            hubspot_tenant,
        ))

    assert result["status"] == "updated"
    assert result["contact_id"] == "456"


@pytest.mark.asyncio
async def test_update_lead_no_fields(hubspot_tenant):
    """update_lead returns error when no update fields provided."""
    with patch("app.agent.tools._get_crm_credentials", return_value="fake-api-key"):
        result = json.loads(await execute_tool(
            "update_lead",
            {"contact_id": "456"},
            hubspot_tenant,
        ))

    assert "error" in result
    assert "No fields" in result["error"]


@pytest.mark.asyncio
async def test_update_lead_missing_contact_id(hubspot_tenant):
    """update_lead returns error when contact_id is missing."""
    result = json.loads(await execute_tool(
        "update_lead",
        {"email": "new@example.com"},
        hubspot_tenant,
    ))
    assert "error" in result
    assert "contact_id" in result["error"]


@pytest.mark.asyncio
async def test_update_lead_google_sheets(sheets_tenant):
    """update_lead returns error for Google Sheets (unsupported)."""
    with patch("app.agent.tools._get_crm_credentials", return_value='{"sheet_id":"x"}'):
        result = json.loads(await execute_tool(
            "update_lead",
            {"contact_id": "1", "email": "new@example.com"},
            sheets_tenant,
        ))

    assert "error" in result
    assert "does not support" in result["error"]


@pytest.mark.asyncio
async def test_update_lead_no_crm(no_crm_tenant):
    """update_lead returns error when no CRM configured."""
    result = json.loads(await execute_tool(
        "update_lead",
        {"contact_id": "1", "email": "new@example.com"},
        no_crm_tenant,
    ))
    assert "error" in result
