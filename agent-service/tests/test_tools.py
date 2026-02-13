import json

import pytest

from app.agent.tools import TOOL_REGISTRY, execute_tool, get_tools_for_tenant
from app.models.tenant import Tenant


def test_echo_tool_registered():
    assert "echo" in TOOL_REGISTRY
    assert "escalate_to_human" in TOOL_REGISTRY


def test_echo_tool_schema():
    schema = TOOL_REGISTRY["echo"].schema
    assert schema["name"] == "echo"
    assert "input_schema" in schema
    assert "message" in schema["input_schema"]["properties"]


@pytest.mark.asyncio
async def test_echo_tool_execution(test_tenant):
    result = await execute_tool("echo", {"message": "hello"}, test_tenant)
    parsed = json.loads(result)
    assert parsed["echoed"] == "hello"


@pytest.mark.asyncio
async def test_escalate_tool_execution(test_tenant):
    result = await execute_tool(
        "escalate_to_human",
        {"reason": "customer wants refund"},
        test_tenant,
    )
    parsed = json.loads(result)
    assert parsed["status"] == "escalated"


@pytest.mark.asyncio
async def test_unknown_tool(test_tenant):
    result = await execute_tool("nonexistent", {}, test_tenant)
    parsed = json.loads(result)
    assert "error" in parsed
    assert "Unknown tool" in parsed["error"]


def test_get_tools_for_tenant_all(test_tenant):
    """When no tools_config, returns all registered tools."""
    tools = get_tools_for_tenant(test_tenant)
    assert len(tools) == len(TOOL_REGISTRY)


def test_get_tools_for_tenant_filtered(test_tenant):
    """When tools_config.enabled is set, returns only those tools."""
    test_tenant.tools_config = {"enabled": ["echo"]}
    tools = get_tools_for_tenant(test_tenant)
    assert len(tools) == 1
    assert tools[0]["name"] == "echo"
