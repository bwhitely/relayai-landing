import json
import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.agent.tools import execute_tool
from app.integrations.slack import send_escalation_notification, send_slack_message
from app.models.tenant import CRMType, Tenant


class TestSendSlackMessage:
    @pytest.mark.asyncio
    async def test_sends_text_message(self):
        mock_response = httpx.Response(
            200,
            text="ok",
            request=httpx.Request("POST", "https://hooks.slack.com/services/test"),
        )

        with patch("app.integrations.slack.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await send_slack_message(
                webhook_url="https://hooks.slack.com/services/test",
                text="Hello from tests",
            )

        assert result["status"] == "sent"
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert call_kwargs.kwargs["json"]["text"] == "Hello from tests"

    @pytest.mark.asyncio
    async def test_sends_with_blocks(self):
        mock_response = httpx.Response(
            200,
            text="ok",
            request=httpx.Request("POST", "https://hooks.slack.com/services/test"),
        )

        with patch("app.integrations.slack.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Test"}}]
            result = await send_slack_message(
                webhook_url="https://hooks.slack.com/services/test",
                text="Fallback",
                blocks=blocks,
            )

        assert result["status"] == "sent"
        call_kwargs = mock_client.post.call_args
        assert "blocks" in call_kwargs.kwargs["json"]


class TestSendEscalationNotification:
    @pytest.mark.asyncio
    async def test_sends_formatted_escalation(self):
        mock_response = httpx.Response(
            200,
            text="ok",
            request=httpx.Request("POST", "https://hooks.slack.com/services/test"),
        )

        with patch("app.integrations.slack.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await send_escalation_notification(
                webhook_url="https://hooks.slack.com/services/test",
                tenant_name="Test Business",
                reason="Customer wants refund",
                summary="Customer ordered wrong item",
                sender_id="+61400000000",
            )

        assert result["status"] == "sent"
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs["json"]
        assert "blocks" in payload
        assert "Escalation" in payload["text"]


class TestEscalationToolDispatch:
    @pytest.mark.asyncio
    async def test_escalation_sends_slack(self):
        tenant = Tenant(
            id=uuid.uuid4(),
            name="Test Business",
            crm_type=CRMType.none,
            escalation_config={
                "slack_webhook_url": "https://hooks.slack.com/services/test",
            },
            max_conversations_per_month=100,
            is_active=True,
        )

        mock_response = httpx.Response(
            200,
            text="ok",
            request=httpx.Request("POST", "https://hooks.slack.com/services/test"),
        )

        with patch("app.integrations.slack.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result_str = await execute_tool(
                "escalate_to_human",
                {"reason": "Customer wants refund", "sender_id": "+61400000000"},
                tenant,
            )

        result = json.loads(result_str)
        assert result["status"] == "escalated"
        assert "slack" in result["notified_via"]

    @pytest.mark.asyncio
    async def test_escalation_no_config(self):
        tenant = Tenant(
            id=uuid.uuid4(),
            name="Test Business",
            crm_type=CRMType.none,
            escalation_config=None,
            max_conversations_per_month=100,
            is_active=True,
        )

        result_str = await execute_tool(
            "escalate_to_human",
            {"reason": "Customer wants refund"},
            tenant,
        )

        result = json.loads(result_str)
        assert result["status"] == "escalated"
        assert "notified_via" not in result

    @pytest.mark.asyncio
    async def test_escalation_slack_failure_graceful(self):
        tenant = Tenant(
            id=uuid.uuid4(),
            name="Test Business",
            crm_type=CRMType.none,
            escalation_config={
                "slack_webhook_url": "https://hooks.slack.com/services/test",
            },
            max_conversations_per_month=100,
            is_active=True,
        )

        with patch("app.integrations.slack.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result_str = await execute_tool(
                "escalate_to_human",
                {"reason": "Customer wants refund"},
                tenant,
            )

        result = json.loads(result_str)
        assert result["status"] == "escalated"
        assert "notification_errors" in result
