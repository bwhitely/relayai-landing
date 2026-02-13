import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, override_settings
from app.models.tenant import CRMType, Tenant


@pytest.fixture(autouse=True)
def mock_settings():
    settings = Settings(
        database_url="postgresql+asyncpg://test:test@localhost:5432/test",
        anthropic_api_key="test-key",
        admin_api_key="test-admin-key",
        twilio_account_sid="ACtest",
        twilio_auth_token="test-auth-token",
        fernet_key="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleTA9PQ==",
        default_model="claude-sonnet-4-5-20250514",
        max_agent_iterations=5,
        agent_timeout_seconds=30,
    )
    override_settings(settings)
    return settings


@pytest.fixture
def test_tenant() -> Tenant:
    return Tenant(
        id=uuid.uuid4(),
        name="Test Business",
        twilio_phone_number="+61400000000",
        system_prompt=None,
        tools_config=None,
        crm_type=CRMType.none,
        max_conversations_per_month=100,
        is_active=True,
        api_key="test-tenant-api-key",
    )


@pytest.fixture
def client():
    """Test client that doesn't require a real database."""
    from app.main import app
    return TestClient(app)
