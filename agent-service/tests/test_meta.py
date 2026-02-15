import hashlib
import hmac
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.meta import (
    META_MESSAGE_LIMIT,
    parse_meta_webhook,
    send_meta_message,
    validate_meta_signature,
)
from app.models.tenant import Tenant, CRMType


# --- Integration module tests ---


def test_validate_meta_signature_valid():
    body = b'{"test": "data"}'
    app_secret = "test-secret"
    expected = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    signature = f"sha256={expected}"
    assert validate_meta_signature(body, signature, app_secret) is True


def test_validate_meta_signature_invalid():
    body = b'{"test": "data"}'
    assert validate_meta_signature(body, "sha256=wrong", "test-secret") is False


def test_validate_meta_signature_missing_prefix():
    body = b'{"test": "data"}'
    app_secret = "test-secret"
    expected = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    assert validate_meta_signature(body, expected, app_secret) is False


@pytest.mark.asyncio
async def test_send_meta_message():
    mock_response = MagicMock()
    mock_response.json.return_value = {"message_id": "mid.123"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.integrations.meta.httpx.AsyncClient", return_value=mock_client):
        results = await send_meta_message("user123", "Hello!", "page456", "token789")

    assert len(results) == 1
    assert results[0]["message_id"] == "mid.123"

    call_args = mock_client.post.call_args
    assert "page456/messages" in call_args[0][0]
    assert call_args[1]["json"]["recipient"]["id"] == "user123"
    assert call_args[1]["json"]["message"]["text"] == "Hello!"
    assert call_args[1]["headers"]["Authorization"] == "Bearer token789"


@pytest.mark.asyncio
async def test_send_meta_message_splits_long_text():
    mock_response = MagicMock()
    mock_response.json.return_value = {"message_id": "mid.123"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    long_text = "a" * 3000

    with patch("app.integrations.meta.httpx.AsyncClient", return_value=mock_client):
        results = await send_meta_message("user123", long_text, "page456", "token789")

    assert mock_client.post.call_count == 2
    assert len(results) == 2


def test_parse_meta_webhook_messenger():
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "page123",
                "messaging": [
                    {
                        "sender": {"id": "user456"},
                        "recipient": {"id": "page123"},
                        "message": {"mid": "mid.1", "text": "Hello there"},
                    }
                ],
            }
        ],
    }
    events = parse_meta_webhook(payload)
    assert len(events) == 1
    assert events[0]["sender_id"] == "user456"
    assert events[0]["recipient_id"] == "page123"
    assert events[0]["text"] == "Hello there"
    assert events[0]["channel"] == "facebook"


def test_parse_meta_webhook_instagram():
    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "ig123",
                "messaging": [
                    {
                        "sender": {"id": "iguser789"},
                        "recipient": {"id": "ig123"},
                        "message": {"mid": "mid.2", "text": "Hey from IG"},
                    }
                ],
            }
        ],
    }
    events = parse_meta_webhook(payload)
    assert len(events) == 1
    assert events[0]["channel"] == "instagram"
    assert events[0]["text"] == "Hey from IG"


def test_parse_meta_webhook_no_text():
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "page123",
                "messaging": [
                    {
                        "sender": {"id": "user456"},
                        "recipient": {"id": "page123"},
                        "message": {"mid": "mid.3", "attachments": [{"type": "image"}]},
                    }
                ],
            }
        ],
    }
    events = parse_meta_webhook(payload)
    assert len(events) == 0


def test_parse_meta_webhook_unknown_object():
    payload = {"object": "unknown", "entry": []}
    events = parse_meta_webhook(payload)
    assert len(events) == 0


# --- Webhook endpoint tests ---


_META_CREDS = json.dumps({
    "app_secret": "test-app-secret",
    "page_access_token": "test-page-token",
    "verify_token": "test-verify-token",
})

# Store as "encrypted-meta-creds" and mock decrypt in tests
_ENCRYPTED_META_CREDS = "encrypted-meta-creds"


def _make_meta_tenant(tenant_id=None, page_id="page123"):
    """Create a test tenant with meta credentials."""
    tenant = Tenant(
        id=tenant_id or uuid.uuid4(),
        name="Meta Test Business",
        crm_type=CRMType.none,
        max_conversations_per_month=100,
        is_active=True,
        api_key="test-meta-key",
        meta_page_id=page_id,
        meta_credentials=_ENCRYPTED_META_CREDS,
    )
    return tenant


def test_meta_verify_valid_token(client):
    from app.database import get_db
    from app.main import app

    tenant = _make_meta_tenant()

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [tenant]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    async def mock_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = mock_get_db

    try:
        with patch("app.routers.webhooks.decrypt", return_value=_META_CREDS):
            response = client.get(
                "/webhooks/meta",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": "test-verify-token",
                    "hub.challenge": "challenge123",
                },
            )
        assert response.status_code == 200
        assert response.text == "challenge123"
    finally:
        app.dependency_overrides.clear()


def test_meta_verify_invalid_token(client):
    from app.database import get_db
    from app.main import app

    tenant = _make_meta_tenant()

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [tenant]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    async def mock_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = mock_get_db

    try:
        with patch("app.routers.webhooks.decrypt", return_value=_META_CREDS):
            response = client.get(
                "/webhooks/meta",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": "wrong-token",
                    "hub.challenge": "challenge123",
                },
            )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_meta_webhook_invalid_signature(client):
    from app.database import get_db
    from app.main import app

    tenant = _make_meta_tenant()

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=tenant))
    )
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    async def mock_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = mock_get_db

    payload = {
        "object": "page",
        "entry": [{"id": "page123", "messaging": []}],
    }

    try:
        with patch("app.routers.webhooks.decrypt", return_value=_META_CREDS), \
             patch("app.routers.webhooks._process_meta_message") as mock_process:
            response = client.post(
                "/webhooks/meta",
                json=payload,
                headers={"X-Hub-Signature-256": "sha256=invalid"},
            )
            assert response.status_code == 200
            mock_process.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_meta_webhook_unknown_page(client):
    from app.database import get_db
    from app.main import app

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    async def mock_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = mock_get_db

    payload = {
        "object": "page",
        "entry": [{"id": "unknown_page", "messaging": []}],
    }

    try:
        response = client.post(
            "/webhooks/meta",
            json=payload,
            headers={"X-Hub-Signature-256": "sha256=whatever"},
        )
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_meta_webhook_processes_message(client):
    from app.database import get_db
    from app.main import app

    tenant = _make_meta_tenant()
    app_secret = "test-app-secret"

    payload = {
        "object": "page",
        "entry": [
            {
                "id": "page123",
                "messaging": [
                    {
                        "sender": {"id": "user999"},
                        "recipient": {"id": "page123"},
                        "message": {"mid": "mid.1", "text": "Hi there"},
                    }
                ],
            }
        ],
    }
    body = json.dumps(payload).encode()
    sig = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=tenant))
    )
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    async def mock_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = mock_get_db

    try:
        with patch("app.routers.webhooks.decrypt", return_value=_META_CREDS), \
             patch("app.routers.webhooks._process_meta_message", new_callable=AsyncMock) as mock_process, \
             patch("asyncio.create_task") as mock_create_task:
            mock_create_task.side_effect = lambda coro: coro.close()

            response = client.post(
                "/webhooks/meta",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": f"sha256={sig}",
                },
            )
            assert response.status_code == 200
            assert mock_create_task.called
    finally:
        app.dependency_overrides.clear()
