from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


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
