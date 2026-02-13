import json
import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.agent.tools import execute_tool
from app.integrations.email import send_email
from app.models.tenant import CRMType, Tenant


class TestSendEmail:
    @pytest.mark.asyncio
    async def test_sends_email_successfully(self):
        mock_response = httpx.Response(
            200,
            json={"id": "email-123"},
            request=httpx.Request("POST", "https://api.resend.com/emails"),
        )

        with patch("app.integrations.email.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await send_email(
                api_key="test-key",
                from_addr="test@relayai.com.au",
                to="customer@example.com",
                subject="Test Subject",
                html_body="<p>Hello</p>",
            )

        assert result["status"] == "sent"
        assert result["email_id"] == "email-123"
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs["json"]
        assert payload["to"] == ["customer@example.com"]
        assert payload["subject"] == "Test Subject"

    @pytest.mark.asyncio
    async def test_sends_with_text_body(self):
        mock_response = httpx.Response(
            200,
            json={"id": "email-456"},
            request=httpx.Request("POST", "https://api.resend.com/emails"),
        )

        with patch("app.integrations.email.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await send_email(
                api_key="test-key",
                from_addr="test@relayai.com.au",
                to="customer@example.com",
                subject="Test",
                html_body="<p>Hello</p>",
                text_body="Hello",
            )

        assert result["status"] == "sent"
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs["json"]
        assert payload["text"] == "Hello"


class TestSendEmailTool:
    @pytest.mark.asyncio
    async def test_send_email_tool(self):
        tenant = Tenant(
            id=uuid.uuid4(),
            name="Test Business",
            crm_type=CRMType.none,
            max_conversations_per_month=100,
            is_active=True,
        )

        mock_response = httpx.Response(
            200,
            json={"id": "email-789"},
            request=httpx.Request("POST", "https://api.resend.com/emails"),
        )

        with patch("app.integrations.email.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result_str = await execute_tool(
                "send_email",
                {
                    "to_email": "customer@example.com",
                    "subject": "Appointment Confirmation",
                    "body": "<p>Your appointment is confirmed.</p>",
                },
                tenant,
            )

        result = json.loads(result_str)
        assert result["status"] == "sent"
        assert result["email_id"] == "email-789"

    @pytest.mark.asyncio
    async def test_send_email_missing_fields(self):
        tenant = Tenant(
            id=uuid.uuid4(),
            name="Test Business",
            crm_type=CRMType.none,
            max_conversations_per_month=100,
            is_active=True,
        )

        result_str = await execute_tool(
            "send_email",
            {"to_email": "customer@example.com"},
            tenant,
        )
        result = json.loads(result_str)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_send_email_no_api_key(self):
        from app.config import Settings, override_settings

        # Override with no resend key
        settings = Settings(
            database_url="postgresql+asyncpg://test:test@localhost:5432/test",
            anthropic_api_key="test-key",
            admin_api_key="test-admin-key",
            fernet_key="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleTA9PQ==",
            resend_api_key="",
        )
        override_settings(settings)

        tenant = Tenant(
            id=uuid.uuid4(),
            name="Test Business",
            crm_type=CRMType.none,
            escalation_config=None,
            max_conversations_per_month=100,
            is_active=True,
        )

        result_str = await execute_tool(
            "send_email",
            {
                "to_email": "customer@example.com",
                "subject": "Test",
                "body": "<p>Hello</p>",
            },
            tenant,
        )
        result = json.loads(result_str)
        assert "error" in result
        assert "Resend" in result["error"]


class TestEscalationWithEmail:
    @pytest.mark.asyncio
    async def test_escalation_sends_both_slack_and_email(self):
        tenant = Tenant(
            id=uuid.uuid4(),
            name="Test Business",
            crm_type=CRMType.none,
            escalation_config={
                "slack_webhook_url": "https://hooks.slack.com/services/test",
                "email": "owner@business.com",
            },
            max_conversations_per_month=100,
            is_active=True,
        )

        slack_response = httpx.Response(
            200,
            text="ok",
            request=httpx.Request("POST", "https://hooks.slack.com/services/test"),
        )
        email_response = httpx.Response(
            200,
            json={"id": "email-esc"},
            request=httpx.Request("POST", "https://api.resend.com/emails"),
        )

        with patch("app.integrations.slack.httpx.AsyncClient") as mock_slack_cls, \
             patch("app.integrations.email.httpx.AsyncClient") as mock_email_cls:
            # Mock Slack
            mock_slack = AsyncMock()
            mock_slack.post = AsyncMock(return_value=slack_response)
            mock_slack.__aenter__ = AsyncMock(return_value=mock_slack)
            mock_slack.__aexit__ = AsyncMock(return_value=False)
            mock_slack_cls.return_value = mock_slack

            # Mock Email
            mock_email = AsyncMock()
            mock_email.post = AsyncMock(return_value=email_response)
            mock_email.__aenter__ = AsyncMock(return_value=mock_email)
            mock_email.__aexit__ = AsyncMock(return_value=False)
            mock_email_cls.return_value = mock_email

            result_str = await execute_tool(
                "escalate_to_human",
                {"reason": "Complex issue", "sender_id": "+61400000000"},
                tenant,
            )

        result = json.loads(result_str)
        assert result["status"] == "escalated"
        assert "slack" in result["notified_via"]
        assert "email" in result["notified_via"]
