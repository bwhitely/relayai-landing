import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.tools import execute_tool
from app.models.tenant import CalendarType, CRMType, Tenant


@pytest.fixture
def gcal_tenant() -> Tenant:
    return Tenant(
        name="Adelaide Trades Co",
        crm_type=CRMType.hubspot,
        crm_credentials="encrypted-hubspot-creds",
        calendar_type=CalendarType.google_calendar,
        calendar_credentials="encrypted-gcal-creds",
        is_active=True,
        max_conversations_per_month=100,
    )


@pytest.fixture
def splose_tenant() -> Tenant:
    return Tenant(
        name="Adelaide Physio",
        crm_type=CRMType.splose,
        crm_credentials="encrypted-splose-creds",
        calendar_type=CalendarType.none,
        is_active=True,
        max_conversations_per_month=100,
    )


GCAL_CREDS = json.dumps({
    "client_email": "relay@project.iam.gserviceaccount.com",
    "private_key": "-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----\n",
    "calendar_id": "someone@gmail.com",
})

SPLOSE_CREDS = json.dumps({
    "api_key": "fake-splose-key",
    "default_practitioner_id": 1,
    "default_service_id": 5,
    "default_location_id": 2,
})


# --- Google Calendar client tests ---

@pytest.mark.asyncio
async def test_google_calendar_check_availability():
    from app.integrations.google_calendar import check_availability

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "kind": "calendar#freeBusy",
        "calendars": {
            "someone@gmail.com": {
                "busy": [
                    {"start": "2024-01-15T09:00:00+10:30", "end": "2024-01-15T10:00:00+10:30"},
                    {"start": "2024-01-15T14:00:00+10:30", "end": "2024-01-15T15:00:00+10:30"},
                ]
            }
        },
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with (
        patch("app.integrations.google_calendar.httpx.AsyncClient", return_value=mock_client),
        patch("app.integrations.google_calendar.get_access_token", return_value="fake-token"),
    ):
        result = await check_availability(
            calendar_id="someone@gmail.com",
            start="2024-01-15T00:00:00+10:30",
            end="2024-01-16T00:00:00+10:30",
            creds_dict=json.loads(GCAL_CREDS),
        )

    assert len(result) == 2
    assert result[0]["start"] == "2024-01-15T09:00:00+10:30"
    assert result[1]["end"] == "2024-01-15T15:00:00+10:30"

    # Verify freebusy was called with correct body
    call_json = mock_client.post.call_args.kwargs["json"]
    assert call_json["items"] == [{"id": "someone@gmail.com"}]


@pytest.mark.asyncio
async def test_google_calendar_create_event():
    from app.integrations.google_calendar import create_event

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "id": "event123",
        "summary": "Appointment - John Smith",
        "start": {"dateTime": "2024-01-15T09:00:00+10:30"},
        "end": {"dateTime": "2024-01-15T10:00:00+10:30"},
        "htmlLink": "https://calendar.google.com/event?eid=abc",
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with (
        patch("app.integrations.google_calendar.httpx.AsyncClient", return_value=mock_client),
        patch("app.integrations.google_calendar.get_access_token", return_value="fake-token"),
    ):
        result = await create_event(
            calendar_id="someone@gmail.com",
            summary="Appointment - John Smith",
            start="2024-01-15T09:00:00+10:30",
            end="2024-01-15T10:00:00+10:30",
            creds_dict=json.loads(GCAL_CREDS),
            description="Initial consultation",
        )

    assert result["status"] == "booked"
    assert result["event_id"] == "event123"
    assert result["summary"] == "Appointment - John Smith"

    # Verify event body
    call_json = mock_client.post.call_args.kwargs["json"]
    assert call_json["summary"] == "Appointment - John Smith"
    assert call_json["description"] == "Initial consultation"
    assert call_json["start"]["dateTime"] == "2024-01-15T09:00:00+10:30"


@pytest.mark.asyncio
async def test_google_calendar_list_events():
    from app.integrations.google_calendar import list_events

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [
            {
                "id": "event1",
                "summary": "Meeting",
                "start": {"dateTime": "2024-01-15T09:00:00+10:30"},
                "end": {"dateTime": "2024-01-15T10:00:00+10:30"},
            },
            {
                "id": "event2",
                "summary": "Lunch",
                "start": {"dateTime": "2024-01-15T12:00:00+10:30"},
                "end": {"dateTime": "2024-01-15T13:00:00+10:30"},
            },
        ],
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with (
        patch("app.integrations.google_calendar.httpx.AsyncClient", return_value=mock_client),
        patch("app.integrations.google_calendar.get_access_token", return_value="fake-token"),
    ):
        result = await list_events(
            calendar_id="someone@gmail.com",
            time_min="2024-01-15T00:00:00+10:30",
            time_max="2024-01-16T00:00:00+10:30",
            creds_dict=json.loads(GCAL_CREDS),
        )

    assert len(result) == 2
    assert result[0]["summary"] == "Meeting"
    assert result[1]["id"] == "event2"


# --- Tool dispatch tests ---

@pytest.mark.asyncio
async def test_check_availability_google_calendar_dispatch(gcal_tenant):
    """check_availability dispatches to Google Calendar when calendar_type is google_calendar."""
    mock_gcal_check = AsyncMock(return_value=[
        {"start": "2024-01-15T09:00:00+10:30", "end": "2024-01-15T10:00:00+10:30"},
    ])

    with (
        patch("app.agent.tools._get_calendar_credentials", return_value=GCAL_CREDS),
        patch("app.integrations.google_calendar.check_availability", mock_gcal_check),
    ):
        result = json.loads(await execute_tool(
            "check_availability",
            {"start_date": "2024-01-15T00:00:00+10:30", "end_date": "2024-01-22T00:00:00+10:30"},
            gcal_tenant,
        ))

    assert result["count"] == 1
    assert "busy_periods" in result
    mock_gcal_check.assert_called_once()
    call_kwargs = mock_gcal_check.call_args.kwargs
    assert call_kwargs["calendar_id"] == "someone@gmail.com"


@pytest.mark.asyncio
async def test_book_appointment_google_calendar(gcal_tenant):
    """book_appointment dispatches to Google Calendar create_event."""
    mock_create = AsyncMock(return_value={
        "status": "booked",
        "event_id": "event123",
        "summary": "Appointment - John Smith",
        "start": "2024-01-15T09:00:00+10:30",
        "end": "2024-01-15T10:00:00+10:30",
        "html_link": "https://calendar.google.com/event?eid=abc",
    })

    with (
        patch("app.agent.tools._get_calendar_credentials", return_value=GCAL_CREDS),
        patch("app.integrations.google_calendar.create_event", mock_create),
    ):
        result = json.loads(await execute_tool(
            "book_appointment",
            {
                "summary": "Appointment - John Smith",
                "start": "2024-01-15T09:00:00+10:30",
                "end": "2024-01-15T10:00:00+10:30",
                "description": "Initial consultation",
            },
            gcal_tenant,
        ))

    assert result["status"] == "booked"
    assert result["event_id"] == "event123"
    mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_check_availability_falls_back_to_splose(splose_tenant):
    """check_availability falls back to Splose when calendar_type=none and crm_type=splose."""
    mock_splose_check = AsyncMock(return_value=[
        {"date": "2024-01-15", "start_time": "09:00", "end_time": "17:00", "location_id": 2},
    ])

    with (
        patch("app.agent.tools._get_crm_credentials", return_value=SPLOSE_CREDS),
        patch("app.integrations.splose.check_availability", mock_splose_check),
    ):
        result = json.loads(await execute_tool(
            "check_availability",
            {"start_date": "2024-01-15T00:00:00.000Z", "end_date": "2024-01-22T00:00:00.000Z"},
            splose_tenant,
        ))

    assert result["count"] == 1
    assert "slots" in result
    mock_splose_check.assert_called_once()


@pytest.mark.asyncio
async def test_book_appointment_splose_dispatch(splose_tenant):
    """book_appointment dispatches to Splose create_appointment."""
    mock_create = AsyncMock(return_value={
        "status": "booked",
        "appointment_id": 99,
        "start": "2024-01-15T09:00:00.000Z",
        "end": "2024-01-15T10:00:00.000Z",
        "practitioner_id": 1,
    })

    with (
        patch("app.agent.tools._get_crm_credentials", return_value=SPLOSE_CREDS),
        patch("app.integrations.splose.create_appointment", mock_create),
    ):
        result = json.loads(await execute_tool(
            "book_appointment",
            {
                "summary": "Physio Session",
                "start": "2024-01-15T09:00:00.000Z",
                "end": "2024-01-15T10:00:00.000Z",
                "patient_id": 42,
            },
            splose_tenant,
        ))

    assert result["status"] == "booked"
    assert result["appointment_id"] == 99
    mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_book_appointment_no_integration(test_tenant):
    """book_appointment returns error when no calendar or booking integration is configured."""
    result = json.loads(await execute_tool(
        "book_appointment",
        {
            "summary": "Test",
            "start": "2024-01-15T09:00:00.000Z",
            "end": "2024-01-15T10:00:00.000Z",
        },
        test_tenant,
    ))
    assert "error" in result


@pytest.mark.asyncio
async def test_book_appointment_missing_times(gcal_tenant):
    """book_appointment requires both start and end times."""
    result = json.loads(await execute_tool(
        "book_appointment",
        {"summary": "Test", "start": "2024-01-15T09:00:00.000Z"},
        gcal_tenant,
    ))
    assert "error" in result


@pytest.mark.asyncio
async def test_book_appointment_splose_requires_patient_id(splose_tenant):
    """book_appointment with Splose requires patient_id."""
    with patch("app.agent.tools._get_crm_credentials", return_value=SPLOSE_CREDS):
        result = json.loads(await execute_tool(
            "book_appointment",
            {
                "summary": "Physio Session",
                "start": "2024-01-15T09:00:00.000Z",
                "end": "2024-01-15T10:00:00.000Z",
            },
            splose_tenant,
        ))
    assert "error" in result
    assert "patient_id" in result["error"]


@pytest.mark.asyncio
async def test_check_availability_no_integration(test_tenant):
    """check_availability returns error when no calendar or CRM is configured."""
    result = json.loads(await execute_tool(
        "check_availability",
        {"start_date": "2024-01-15T00:00:00.000Z", "end_date": "2024-01-22T00:00:00.000Z"},
        test_tenant,
    ))
    assert "error" in result


# --- Google Calendar delete_event tests ---

@pytest.mark.asyncio
async def test_google_calendar_delete_event():
    from app.integrations.google_calendar import delete_event

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.delete = AsyncMock(return_value=mock_response)

    with (
        patch("app.integrations.google_calendar.httpx.AsyncClient", return_value=mock_client),
        patch("app.integrations.google_calendar.get_access_token", return_value="fake-token"),
    ):
        result = await delete_event(
            calendar_id="someone@gmail.com",
            event_id="event123",
            creds_dict=json.loads(GCAL_CREDS),
        )

    assert result["status"] == "cancelled"
    assert result["event_id"] == "event123"
    mock_client.delete.assert_called_once()


# --- list_appointments tool dispatch tests ---

@pytest.mark.asyncio
async def test_list_appointments_google_calendar_dispatch(gcal_tenant):
    """list_appointments dispatches to Google Calendar list_events."""
    mock_list = AsyncMock(return_value=[
        {"id": "event1", "summary": "Appointment - Jane", "start": "2024-01-15T09:00:00+10:30", "end": "2024-01-15T10:00:00+10:30"},
    ])

    with (
        patch("app.agent.tools._get_calendar_credentials", return_value=GCAL_CREDS),
        patch("app.integrations.google_calendar.list_events", mock_list),
    ):
        result = json.loads(await execute_tool(
            "list_appointments",
            {"start_date": "2024-01-15T00:00:00+10:30", "end_date": "2024-01-22T00:00:00+10:30"},
            gcal_tenant,
        ))

    assert result["count"] == 1
    assert result["appointments"][0]["summary"] == "Appointment - Jane"
    mock_list.assert_called_once()


@pytest.mark.asyncio
async def test_list_appointments_splose_dispatch(splose_tenant):
    """list_appointments dispatches to Splose list_appointments."""
    mock_list = AsyncMock(return_value=[
        {"appointment_id": 55, "start": "2024-01-15T09:00:00.000Z", "end": "2024-01-15T10:00:00.000Z", "practitioner_id": 1, "patient_id": 42, "status": "Confirmed"},
    ])

    with (
        patch("app.agent.tools._get_crm_credentials", return_value=SPLOSE_CREDS),
        patch("app.integrations.splose.list_appointments", mock_list),
    ):
        result = json.loads(await execute_tool(
            "list_appointments",
            {"start_date": "2024-01-15T00:00:00.000Z", "end_date": "2024-01-22T00:00:00.000Z", "patient_id": 42},
            splose_tenant,
        ))

    assert result["count"] == 1
    assert result["appointments"][0]["appointment_id"] == 55
    mock_list.assert_called_once()


@pytest.mark.asyncio
async def test_list_appointments_no_integration(test_tenant):
    """list_appointments returns error when no calendar/CRM configured."""
    result = json.loads(await execute_tool(
        "list_appointments",
        {"start_date": "2024-01-15T00:00:00.000Z", "end_date": "2024-01-22T00:00:00.000Z"},
        test_tenant,
    ))
    assert "error" in result


@pytest.mark.asyncio
async def test_list_appointments_missing_dates(gcal_tenant):
    """list_appointments requires both start_date and end_date."""
    result = json.loads(await execute_tool(
        "list_appointments",
        {"start_date": "2024-01-15T00:00:00.000Z"},
        gcal_tenant,
    ))
    assert "error" in result


# --- cancel_appointment tool dispatch tests ---

@pytest.mark.asyncio
async def test_cancel_appointment_google_calendar(gcal_tenant):
    """cancel_appointment dispatches to Google Calendar delete_event."""
    mock_delete = AsyncMock(return_value={
        "status": "cancelled",
        "event_id": "event123",
    })

    with (
        patch("app.agent.tools._get_calendar_credentials", return_value=GCAL_CREDS),
        patch("app.integrations.google_calendar.delete_event", mock_delete),
    ):
        result = json.loads(await execute_tool(
            "cancel_appointment",
            {"appointment_id": "event123", "reason": "Customer requested"},
            gcal_tenant,
        ))

    assert result["status"] == "cancelled"
    assert result["event_id"] == "event123"
    mock_delete.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_appointment_splose(splose_tenant):
    """cancel_appointment dispatches to Splose cancel_appointment."""
    mock_cancel = AsyncMock(return_value={
        "status": "cancelled",
        "appointment_id": 55,
    })

    with (
        patch("app.agent.tools._get_crm_credentials", return_value=SPLOSE_CREDS),
        patch("app.integrations.splose.cancel_appointment", mock_cancel),
    ):
        result = json.loads(await execute_tool(
            "cancel_appointment",
            {"appointment_id": "55", "reason": "Patient unavailable"},
            splose_tenant,
        ))

    assert result["status"] == "cancelled"
    assert result["appointment_id"] == 55
    mock_cancel.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_appointment_no_integration(test_tenant):
    """cancel_appointment returns error when no calendar/CRM configured."""
    result = json.loads(await execute_tool(
        "cancel_appointment",
        {"appointment_id": "123"},
        test_tenant,
    ))
    assert "error" in result


@pytest.mark.asyncio
async def test_cancel_appointment_missing_id(gcal_tenant):
    """cancel_appointment requires appointment_id."""
    result = json.loads(await execute_tool(
        "cancel_appointment",
        {"reason": "No ID given"},
        gcal_tenant,
    ))
    assert "error" in result
