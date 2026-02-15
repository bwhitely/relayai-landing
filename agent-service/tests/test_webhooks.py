import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.routers.webhooks import _extract_tool_calls
from app.schemas.webhook import ToolCallInfo


def test_extract_tool_calls_pairs_use_and_result():
    """_extract_tool_calls extracts tool_use/tool_result pairs from messages."""
    messages = [
        {"role": "user", "content": "Book me in"},
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "tu_1",
                    "name": "check_availability",
                    "input": {"date": "2026-02-15"},
                },
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tu_1",
                    "content": '{"slots": ["9:00", "10:00"]}',
                },
            ],
        },
        {
            "role": "assistant",
            "content": [{"type": "text", "text": "I found 2 slots."}],
        },
    ]
    result = _extract_tool_calls(messages)
    assert len(result) == 1
    assert result[0].tool == "check_availability"
    assert result[0].input == {"date": "2026-02-15"}
    assert result[0].result == {"slots": ["9:00", "10:00"]}


def test_extract_tool_calls_handles_non_json_result():
    """_extract_tool_calls handles non-JSON tool results gracefully."""
    messages = [
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "tu_2", "name": "echo", "input": {"message": "hi"}},
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "tu_2", "content": "Echo: hi"},
            ],
        },
    ]
    result = _extract_tool_calls(messages)
    assert len(result) == 1
    assert result[0].result == "Echo: hi"


def test_extract_tool_calls_empty_messages():
    """_extract_tool_calls returns empty list for messages with no tools."""
    assert _extract_tool_calls([]) == []
    assert _extract_tool_calls([{"role": "user", "content": "hello"}]) == []


def test_generic_webhook_includes_tool_calls(client, test_tenant):
    """Generic webhook returns tool_calls when include_tool_calls=true."""
    from app.agent.loop import AgentResult
    from app.database import get_db
    from app.main import app

    agent_result = AgentResult(
        response_text="I found 2 available slots.",
        messages=[
            {"role": "user", "content": "Check availability"},
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tu_1",
                        "name": "check_availability",
                        "input": {"date": "2026-02-15"},
                    },
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tu_1",
                        "content": '{"slots": ["9:00", "10:00"]}',
                    },
                ],
            },
            {
                "role": "assistant",
                "content": [{"type": "text", "text": "I found 2 available slots."}],
            },
        ],
        total_input_tokens=100,
        total_output_tokens=50,
        total_cost_usd=0.001,
        model="claude-sonnet-4-5-20250514",
        iterations=2,
    )

    mock_conversation = MagicMock()
    mock_conversation.id = uuid.uuid4()
    mock_conversation.messages = []

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=test_tenant)
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    mock_session.flush = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    async def mock_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = mock_get_db

    try:
        with patch("app.routers.webhooks._get_or_create_conversation", return_value=mock_conversation), \
             patch("app.routers.webhooks._check_conversation_limit", return_value=True), \
             patch("app.routers.webhooks.run_agent_loop", return_value=agent_result):
            response = client.post(
                f"/webhooks/generic/{test_tenant.id}?include_tool_calls=true",
                json={"sender_id": "test-user", "message": "Check availability"},
                headers={"X-API-Key": test_tenant.api_key},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["tool_calls"] is not None
        assert len(data["tool_calls"]) == 1
        assert data["tool_calls"][0]["tool"] == "check_availability"
        assert data["iterations"] == 2
    finally:
        app.dependency_overrides.clear()


def test_generic_webhook_excludes_tool_calls_by_default(client, test_tenant):
    """Generic webhook omits tool_calls when include_tool_calls is not set."""
    from app.agent.loop import AgentResult
    from app.database import get_db
    from app.main import app

    agent_result = AgentResult(
        response_text="Hello!",
        messages=[{"role": "user", "content": "hi"}],
        iterations=1,
    )

    mock_conversation = MagicMock()
    mock_conversation.id = uuid.uuid4()
    mock_conversation.messages = []

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=test_tenant)
    mock_session.flush = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    async def mock_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = mock_get_db

    try:
        with patch("app.routers.webhooks._get_or_create_conversation", return_value=mock_conversation), \
             patch("app.routers.webhooks._check_conversation_limit", return_value=True), \
             patch("app.routers.webhooks.run_agent_loop", return_value=agent_result):
            response = client.post(
                f"/webhooks/generic/{test_tenant.id}",
                json={"sender_id": "test-user", "message": "hi"},
                headers={"X-API-Key": test_tenant.api_key},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["tool_calls"] is None
        assert data["iterations"] is None
    finally:
        app.dependency_overrides.clear()


def test_health_check(client):
    """Health endpoint works without database."""
    with patch("app.database.init_db"):
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_admin_requires_api_key(client):
    """Admin endpoints reject requests without API key."""
    with patch("app.database.init_db"):
        response = client.get("/admin/tenants")
    # FastAPI APIKeyHeader returns 403 when header is missing
    assert response.status_code in (401, 403)


def test_admin_rejects_wrong_key(client):
    """Admin endpoints reject invalid API key."""
    with patch("app.database.init_db"):
        response = client.get(
            "/admin/tenants",
            headers={"X-API-Key": "wrong-key"},
        )
    assert response.status_code == 403


def test_admin_accepts_correct_key(client):
    """Admin endpoints accept correct API key (mocked DB)."""
    from app.database import get_db

    from unittest.mock import MagicMock

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    async def mock_get_db():
        yield mock_session

    from app.main import app

    app.dependency_overrides[get_db] = mock_get_db

    try:
        with patch("app.database.init_db"):
            response = client.get(
                "/admin/tenants",
                headers={"X-API-Key": "test-admin-key"},
            )
        assert response.status_code == 200
        assert response.json() == []
    finally:
        app.dependency_overrides.clear()
