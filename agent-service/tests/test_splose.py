import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.tools import execute_tool
from app.models.tenant import CRMType, Tenant


@pytest.fixture
def splose_tenant() -> Tenant:
    return Tenant(
        name="Adelaide Physio",
        crm_type=CRMType.splose,
        crm_credentials="encrypted-splose-creds",
        is_active=True,
        max_conversations_per_month=100,
    )


SPLOSE_CREDS = json.dumps({
    "api_key": "fake-splose-key",
    "default_practitioner_id": 1,
    "default_service_id": 5,
    "default_location_id": 2,
})


# --- Splose client tests ---

@pytest.mark.asyncio
async def test_splose_create_patient():
    from app.integrations.splose import create_patient

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": 42,
        "firstname": "Sarah",
        "lastname": "Jones",
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.integrations.splose.httpx.AsyncClient", return_value=mock_client):
        result = await create_patient(
            {"firstname": "Sarah", "lastname": "Jones", "phone": "0412345678"},
            "fake-key",
        )

    assert result["status"] == "created"
    assert result["patient_id"] == 42

    # Check phone was formatted correctly
    call_json = mock_client.post.call_args.kwargs["json"]
    assert call_json["phoneNumbers"][0]["phoneNumber"] == "0412345678"
    assert call_json["phoneNumbers"][0]["type"] == "Mobile"


@pytest.mark.asyncio
async def test_splose_search_patients_by_phone():
    from app.integrations.splose import search_patients

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {
                "id": 42,
                "firstname": "Sarah",
                "lastname": "Jones",
                "email": "sarah@example.com",
                "phoneNumbers": [{"phoneNumber": "0412345678"}],
            }
        ],
        "links": {},
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("app.integrations.splose.httpx.AsyncClient", return_value=mock_client):
        results = await search_patients("+61412345678", "fake-key")

    assert len(results) == 1
    assert results[0]["patient_id"] == 42
    # Check country code stripped
    call_params = mock_client.get.call_args.kwargs["params"]
    assert call_params["phoneNumber"] == "0412345678"


@pytest.mark.asyncio
async def test_splose_search_patients_by_email():
    from app.integrations.splose import search_patients

    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [], "links": {}}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("app.integrations.splose.httpx.AsyncClient", return_value=mock_client):
        await search_patients("sarah@example.com", "fake-key")

    call_params = mock_client.get.call_args.kwargs["params"]
    assert call_params["email"] == "sarah@example.com"


@pytest.mark.asyncio
async def test_splose_search_patients_by_name():
    from app.integrations.splose import search_patients

    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [], "links": {}}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("app.integrations.splose.httpx.AsyncClient", return_value=mock_client):
        await search_patients("Sarah Jones", "fake-key")

    call_params = mock_client.get.call_args.kwargs["params"]
    assert call_params["firstname"] == "Sarah"
    assert call_params["lastname"] == "Jones"


@pytest.mark.asyncio
async def test_splose_check_availability():
    from app.integrations.splose import check_availability

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {
                "date": "2024-01-15T00:00:00.000Z",
                "startTime": "09:00",
                "endTime": "17:00",
                "locationId": 1,
                "repeatInterval": "Weekly",
            },
            {
                "date": "2024-01-16T00:00:00.000Z",
                "startTime": "10:00",
                "endTime": "14:00",
                "locationId": 1,
                "repeatInterval": None,
            },
        ]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("app.integrations.splose.httpx.AsyncClient", return_value=mock_client):
        slots = await check_availability(
            practitioner_id=1,
            start_date="2024-01-15T00:00:00.000Z",
            end_date="2024-01-22T00:00:00.000Z",
            api_key="fake-key",
        )

    assert len(slots) == 2
    assert slots[0]["start_time"] == "09:00"
    assert slots[1]["start_time"] == "10:00"


@pytest.mark.asyncio
async def test_splose_create_appointment():
    from app.integrations.splose import create_appointment

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "id": 99,
        "start": "2024-01-15T09:00:00.000Z",
        "end": "2024-01-15T10:00:00.000Z",
        "practitionerId": 1,
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.integrations.splose.httpx.AsyncClient", return_value=mock_client):
        result = await create_appointment(
            start="2024-01-15T09:00:00.000Z",
            end="2024-01-15T10:00:00.000Z",
            patient_id=42,
            practitioner_id=1,
            service_id=5,
            location_id=2,
            api_key="fake-key",
        )

    assert result["status"] == "booked"
    assert result["appointment_id"] == 99


@pytest.mark.asyncio
async def test_splose_user_agent_header():
    """Verify User-Agent header is set on all requests (Splose requires it)."""
    from app.integrations.splose import search_patients

    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [], "links": {}}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("app.integrations.splose.httpx.AsyncClient", return_value=mock_client):
        await search_patients("test", "fake-key")

    call_headers = mock_client.get.call_args.kwargs["headers"]
    assert "User-Agent" in call_headers
    assert call_headers["User-Agent"] == "RelayAI-AgentService/1.0"


# --- Tool dispatch tests ---

@pytest.mark.asyncio
async def test_create_lead_splose_dispatch(splose_tenant):
    """create_lead dispatches to Splose create_patient."""
    mock_create = AsyncMock(return_value={
        "status": "created",
        "patient_id": 42,
        "firstname": "Sarah",
        "lastname": "Jones",
    })

    with (
        patch("app.agent.tools._get_crm_credentials", return_value=SPLOSE_CREDS),
        patch("app.integrations.splose.create_patient", mock_create),
    ):
        result = json.loads(await execute_tool(
            "create_lead",
            {"first_name": "Sarah", "last_name": "Jones", "phone": "+61412345678"},
            splose_tenant,
        ))

    assert result["status"] == "created"
    assert result["patient_id"] == 42


@pytest.mark.asyncio
async def test_search_contacts_splose_dispatch(splose_tenant):
    """search_contacts dispatches to Splose search_patients."""
    mock_search = AsyncMock(return_value=[
        {"patient_id": 42, "firstname": "Sarah", "lastname": "Jones", "email": None, "phone": "0412345678"},
    ])

    with (
        patch("app.agent.tools._get_crm_credentials", return_value=SPLOSE_CREDS),
        patch("app.integrations.splose.search_patients", mock_search),
    ):
        result = json.loads(await execute_tool(
            "search_contacts",
            {"query": "+61412345678"},
            splose_tenant,
        ))

    assert result["count"] == 1
    assert result["results"][0]["patient_id"] == 42


@pytest.mark.asyncio
async def test_check_availability_splose(splose_tenant):
    """check_availability calls Splose with default practitioner from config."""
    mock_avail = AsyncMock(return_value=[
        {"date": "2024-01-15", "start_time": "09:00", "end_time": "17:00", "location_id": 2},
    ])

    with (
        patch("app.agent.tools._get_crm_credentials", return_value=SPLOSE_CREDS),
        patch("app.integrations.splose.check_availability", mock_avail),
    ):
        result = json.loads(await execute_tool(
            "check_availability",
            {"start_date": "2024-01-15T00:00:00.000Z", "end_date": "2024-01-22T00:00:00.000Z"},
            splose_tenant,
        ))

    assert result["count"] == 1
    # Should have used default_practitioner_id from creds
    mock_avail.assert_called_once()
    call_kwargs = mock_avail.call_args
    assert call_kwargs.kwargs["practitioner_id"] == 1


@pytest.mark.asyncio
async def test_check_availability_non_splose_tenant(test_tenant):
    """check_availability returns error for non-Splose tenants."""
    result = json.loads(await execute_tool(
        "check_availability",
        {"start_date": "2024-01-15T00:00:00.000Z", "end_date": "2024-01-22T00:00:00.000Z"},
        test_tenant,
    ))
    assert "error" in result


@pytest.mark.asyncio
async def test_check_availability_missing_dates(splose_tenant):
    """check_availability requires both dates."""
    with patch("app.agent.tools._get_crm_credentials", return_value=SPLOSE_CREDS):
        result = json.loads(await execute_tool(
            "check_availability",
            {"start_date": "2024-01-15T00:00:00.000Z"},
            splose_tenant,
        ))
    assert "error" in result


# --- Splose update tests ---

@pytest.mark.asyncio
async def test_splose_update_patient():
    """update_patient GETs current data, merges, then PUTs."""
    from app.integrations.splose import update_patient

    current_patient = {
        "id": 42,
        "firstname": "Sarah",
        "lastname": "Jones",
        "email": "old@example.com",
        "sex": "Female",
        "genderIdentity": "Woman",
        "alert": "",
        "birthdate": "1990-01-01",
        "city": "Adelaide",
        "state": "SA",
        "postalCode": "5000",
        "country": "Australia",
        "phoneNumbers": [{"type": "Mobile", "code": "+61", "phoneNumber": "0412345678"}],
        "privacyPolicy": "Accepted",
        "ndisNumber": "",
        "medicareNum": "",
        "irn": "",
        "veteransFileNumber": "",
        "emergencyContactNumber": "",
        "emergencyContactName": "",
        "emergencyContactRelationship": "",
    }

    # Mock GET for current patient
    get_response = MagicMock()
    get_response.json.return_value = current_patient
    get_response.raise_for_status = MagicMock()

    # Mock PUT response (returns 1)
    put_response = MagicMock()
    put_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=get_response)
    mock_client.put = AsyncMock(return_value=put_response)

    with patch("app.integrations.splose.httpx.AsyncClient", return_value=mock_client):
        result = await update_patient(42, {"email": "new@example.com"}, "fake-key")

    assert result["status"] == "updated"
    assert result["patient_id"] == 42

    # Verify PUT was called with merged data
    put_json = mock_client.put.call_args.kwargs["json"]
    assert put_json["email"] == "new@example.com"
    assert put_json["firstname"] == "Sarah"  # Preserved from GET


@pytest.mark.asyncio
async def test_update_lead_splose_dispatch(splose_tenant):
    """update_lead dispatches to Splose update_patient."""
    mock_update = AsyncMock(return_value={
        "status": "updated",
        "patient_id": 42,
    })

    with (
        patch("app.agent.tools._get_crm_credentials", return_value=SPLOSE_CREDS),
        patch("app.integrations.splose.update_patient", mock_update),
    ):
        result = json.loads(await execute_tool(
            "update_lead",
            {"contact_id": "42", "email": "new@example.com"},
            splose_tenant,
        ))

    assert result["status"] == "updated"
    mock_update.assert_called_once()
    # Verify patient_id was converted to int
    assert mock_update.call_args.args[0] == 42


# --- Splose list/cancel appointment unit tests ---

@pytest.mark.asyncio
async def test_splose_list_appointments():
    from app.integrations.splose import list_appointments

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {
                "id": 101,
                "start": "2024-01-15T09:00:00.000Z",
                "end": "2024-01-15T10:00:00.000Z",
                "practitionerId": 1,
                "patientId": 42,
                "serviceId": 5,
                "locationId": 2,
                "note": "Initial consult",
                "appointmentPatients": [{"status": "Confirmed"}],
            },
            {
                "id": 102,
                "start": "2024-01-16T14:00:00.000Z",
                "end": "2024-01-16T15:00:00.000Z",
                "practitionerId": 1,
                "patientId": 43,
                "serviceId": 5,
                "locationId": 2,
                "note": "",
                "appointmentPatients": [],
            },
        ]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("app.integrations.splose.httpx.AsyncClient", return_value=mock_client):
        results = await list_appointments(
            api_key="fake-key",
            practitioner_id=1,
            start_date="2024-01-15T00:00:00.000Z",
            end_date="2024-01-22T00:00:00.000Z",
        )

    assert len(results) == 2
    assert results[0]["appointment_id"] == 101
    assert results[0]["status"] == "Confirmed"
    assert results[1]["status"] == ""  # No appointmentPatients


@pytest.mark.asyncio
async def test_splose_get_appointment():
    from app.integrations.splose import get_appointment

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "id": 101,
        "start": "2024-01-15T09:00:00.000Z",
        "end": "2024-01-15T10:00:00.000Z",
        "practitionerId": 1,
        "patientId": 42,
        "serviceId": 5,
        "locationId": 2,
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("app.integrations.splose.httpx.AsyncClient", return_value=mock_client):
        result = await get_appointment(101, "fake-key")

    assert result["id"] == 101
    mock_client.get.assert_called_once()
    assert "/appointments/101" in str(mock_client.get.call_args)


@pytest.mark.asyncio
async def test_splose_cancel_appointment():
    from app.integrations.splose import cancel_appointment

    current_appointment = {
        "id": 101,
        "start": "2024-01-15T09:00:00.000Z",
        "end": "2024-01-15T10:00:00.000Z",
        "practitionerId": 1,
        "patientId": 42,
        "serviceId": 5,
        "locationId": 2,
        "note": "Initial consult",
        "appointmentPatients": [{"status": "Confirmed", "patientId": 42}],
    }

    get_response = MagicMock()
    get_response.json.return_value = current_appointment
    get_response.raise_for_status = MagicMock()

    put_response = MagicMock()
    put_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=get_response)
    mock_client.put = AsyncMock(return_value=put_response)

    with patch("app.integrations.splose.httpx.AsyncClient", return_value=mock_client):
        result = await cancel_appointment(101, "fake-key", reason="Patient requested")

    assert result["status"] == "cancelled"
    assert result["appointment_id"] == 101

    # Verify PUT body has cancellation status
    put_json = mock_client.put.call_args.kwargs["json"]
    assert put_json["appointmentPatients"][0]["status"] == "Cancelled"
    assert put_json["appointmentPatients"][0]["cancellationReason"] == "Patient requested"
    assert put_json["note"] == "Initial consult"  # Preserved original note
