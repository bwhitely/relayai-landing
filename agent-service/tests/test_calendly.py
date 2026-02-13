import json
import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.agent.tools import execute_tool
from app.integrations.calendly import get_available_times, get_scheduling_link
from app.models.tenant import CalendarType, CRMType, Tenant


CALENDLY_CREDS = json.dumps({
    "api_key": "test-calendly-key",
    "event_type_uri": "https://api.calendly.com/event_types/abc123",
})


@pytest.fixture
def calendly_tenant() -> Tenant:
    return Tenant(
        id=uuid.uuid4(),
        name="Calendly Business",
        crm_type=CRMType.none,
        calendar_type=CalendarType.calendly,
        calendar_credentials="encrypted-calendly-creds",
        max_conversations_per_month=100,
        is_active=True,
    )


class TestGetAvailableTimes:
    @pytest.mark.asyncio
    async def test_returns_available_slots(self):
        mock_response = httpx.Response(
            200,
            json={
                "collection": [
                    {"start_time": "2024-01-15T09:00:00Z", "status": "available"},
                    {"start_time": "2024-01-15T10:00:00Z", "status": "available"},
                ]
            },
            request=httpx.Request("GET", "https://api.calendly.com/event_type_available_times"),
        )

        with patch("app.integrations.calendly.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await get_available_times(
                event_type_uri="https://api.calendly.com/event_types/abc123",
                start_time="2024-01-15T00:00:00Z",
                end_time="2024-01-22T00:00:00Z",
                api_key="test-key",
            )

        assert len(result) == 2
        assert result[0]["start_time"] == "2024-01-15T09:00:00Z"
        assert result[0]["status"] == "available"

    @pytest.mark.asyncio
    async def test_empty_collection(self):
        mock_response = httpx.Response(
            200,
            json={"collection": []},
            request=httpx.Request("GET", "https://api.calendly.com/event_type_available_times"),
        )

        with patch("app.integrations.calendly.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await get_available_times(
                event_type_uri="https://api.calendly.com/event_types/abc123",
                start_time="2024-01-15T00:00:00Z",
                end_time="2024-01-22T00:00:00Z",
                api_key="test-key",
            )

        assert result == []


class TestGetSchedulingLink:
    @pytest.mark.asyncio
    async def test_returns_scheduling_url(self):
        mock_response = httpx.Response(
            200,
            json={
                "resource": {
                    "scheduling_url": "https://calendly.com/testuser/30min",
                    "name": "30 Minute Meeting",
                    "duration": 30,
                }
            },
            request=httpx.Request("GET", "https://api.calendly.com/event_types/abc123"),
        )

        with patch("app.integrations.calendly.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await get_scheduling_link(
                event_type_uri="https://api.calendly.com/event_types/abc123",
                api_key="test-key",
            )

        assert result["scheduling_url"] == "https://calendly.com/testuser/30min"
        assert result["name"] == "30 Minute Meeting"
        assert result["duration_minutes"] == 30


class TestCalendlyToolDispatch:
    @pytest.mark.asyncio
    async def test_check_availability_calendly(self, calendly_tenant):
        mock_response = httpx.Response(
            200,
            json={
                "collection": [
                    {"start_time": "2024-01-15T09:00:00Z", "status": "available"},
                ]
            },
            request=httpx.Request("GET", "https://api.calendly.com/event_type_available_times"),
        )

        with patch("app.integrations.calendly.httpx.AsyncClient") as mock_client_cls, \
             patch("app.agent.tools._get_calendar_credentials", return_value=CALENDLY_CREDS):
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result_str = await execute_tool(
                "check_availability",
                {"start_date": "2024-01-15T00:00:00Z", "end_date": "2024-01-22T00:00:00Z"},
                calendly_tenant,
            )

        result = json.loads(result_str)
        assert result["count"] == 1
        assert result["slots"][0]["start_time"] == "2024-01-15T09:00:00Z"

    @pytest.mark.asyncio
    async def test_book_appointment_calendly_returns_link(self, calendly_tenant):
        mock_response = httpx.Response(
            200,
            json={
                "resource": {
                    "scheduling_url": "https://calendly.com/testuser/30min",
                    "name": "30 Minute Meeting",
                    "duration": 30,
                }
            },
            request=httpx.Request("GET", "https://api.calendly.com/event_types/abc123"),
        )

        with patch("app.integrations.calendly.httpx.AsyncClient") as mock_client_cls, \
             patch("app.agent.tools._get_calendar_credentials", return_value=CALENDLY_CREDS):
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result_str = await execute_tool(
                "book_appointment",
                {
                    "summary": "Test Appointment",
                    "start": "2024-01-15T09:00:00Z",
                    "end": "2024-01-15T09:30:00Z",
                },
                calendly_tenant,
            )

        result = json.loads(result_str)
        assert result["status"] == "scheduling_link"
        assert result["scheduling_url"] == "https://calendly.com/testuser/30min"

    @pytest.mark.asyncio
    async def test_check_availability_no_event_type_uri(self):
        no_uri_creds = json.dumps({"api_key": "test-key"})
        tenant = Tenant(
            id=uuid.uuid4(),
            name="Bad Config",
            crm_type=CRMType.none,
            calendar_type=CalendarType.calendly,
            calendar_credentials="encrypted-bad-creds",
            max_conversations_per_month=100,
            is_active=True,
        )

        with patch("app.agent.tools._get_calendar_credentials", return_value=no_uri_creds):
            result_str = await execute_tool(
                "check_availability",
                {"start_date": "2024-01-15T00:00:00Z", "end_date": "2024-01-22T00:00:00Z"},
                tenant,
            )
        result = json.loads(result_str)
        assert "error" in result
        assert "event_type_uri" in result["error"]
