from unittest.mock import AsyncMock, patch

import pytest

from app.agent.loop import run_agent_loop


@pytest.mark.asyncio
async def test_simple_text_response(test_tenant):
    """Agent returns a text response with no tool use."""
    mock_response = AsyncMock()
    mock_response.return_value = AsyncMock(
        content=[{"type": "text", "text": "Hello! How can I help?"}],
        stop_reason="end_turn",
        input_tokens=100,
        output_tokens=20,
        model="claude-sonnet-4-5-20250514",
        estimated_cost_usd=0.0006,
    )
    # Make mock_response callable and return itself for attribute access
    from app.integrations.anthropic import LLMResponse

    mock_llm = AsyncMock(return_value=LLMResponse(
        content=[{"type": "text", "text": "Hello! How can I help?"}],
        stop_reason="end_turn",
        input_tokens=100,
        output_tokens=20,
        model="claude-sonnet-4-5-20250514",
        estimated_cost_usd=0.0006,
    ))

    with patch("app.agent.loop.call_llm", mock_llm):
        result = await run_agent_loop(test_tenant, [], "Hi there")

    assert result.response_text == "Hello! How can I help?"
    assert result.total_input_tokens == 100
    assert result.total_output_tokens == 20
    assert result.iterations == 1
    assert len(result.messages) == 2  # user + assistant


@pytest.mark.asyncio
async def test_tool_use_then_text(test_tenant):
    """Agent calls a tool, then returns text."""
    from app.integrations.anthropic import LLMResponse

    tool_use_response = LLMResponse(
        content=[
            {"type": "text", "text": "Let me echo that for you."},
            {
                "type": "tool_use",
                "id": "toolu_123",
                "name": "echo",
                "input": {"message": "test"},
            },
        ],
        stop_reason="tool_use",
        input_tokens=100,
        output_tokens=30,
        model="claude-sonnet-4-5-20250514",
        estimated_cost_usd=0.00075,
    )

    final_response = LLMResponse(
        content=[{"type": "text", "text": "The echo returned: test"}],
        stop_reason="end_turn",
        input_tokens=150,
        output_tokens=15,
        model="claude-sonnet-4-5-20250514",
        estimated_cost_usd=0.000675,
    )

    mock_llm = AsyncMock(side_effect=[tool_use_response, final_response])

    with patch("app.agent.loop.call_llm", mock_llm):
        result = await run_agent_loop(test_tenant, [], "Echo test")

    assert result.response_text == "The echo returned: test"
    assert result.iterations == 2
    assert result.total_input_tokens == 250
    assert result.total_output_tokens == 45
    # messages: user, assistant (tool_use), user (tool_result), assistant (text)
    assert len(result.messages) == 4


@pytest.mark.asyncio
async def test_max_iterations_fallback(test_tenant):
    """Agent hits max iterations and returns fallback."""
    from app.integrations.anthropic import LLMResponse

    # Every response triggers another tool use
    tool_response = LLMResponse(
        content=[
            {
                "type": "tool_use",
                "id": "toolu_loop",
                "name": "echo",
                "input": {"message": "looping"},
            },
        ],
        stop_reason="tool_use",
        input_tokens=50,
        output_tokens=20,
        model="claude-sonnet-4-5-20250514",
        estimated_cost_usd=0.00045,
    )

    mock_llm = AsyncMock(return_value=tool_response)

    mock_settings_obj = AsyncMock()
    mock_settings_obj.max_agent_iterations = 3
    mock_settings_obj.agent_timeout_seconds = 30
    mock_settings_obj.default_model = "claude-sonnet-4-5-20250514"

    with (
        patch("app.agent.loop.call_llm", mock_llm),
        patch("app.agent.loop.get_settings", return_value=mock_settings_obj),
    ):
        result = await run_agent_loop(test_tenant, [], "Loop forever")

    assert "sorry" in result.response_text.lower()
    assert result.iterations == 3


@pytest.mark.asyncio
async def test_conversation_history_preserved(test_tenant):
    """Existing conversation history is carried forward."""
    from app.integrations.anthropic import LLMResponse

    existing_messages = [
        {"role": "user", "content": "Previous message"},
        {"role": "assistant", "content": [{"type": "text", "text": "Previous reply"}]},
    ]

    mock_llm = AsyncMock(return_value=LLMResponse(
        content=[{"type": "text", "text": "Follow-up reply"}],
        stop_reason="end_turn",
        input_tokens=200,
        output_tokens=15,
        model="claude-sonnet-4-5-20250514",
        estimated_cost_usd=0.000825,
    ))

    with patch("app.agent.loop.call_llm", mock_llm):
        result = await run_agent_loop(test_tenant, existing_messages, "Follow up")

    # 2 existing + 1 new user + 1 new assistant = 4
    assert len(result.messages) == 4
    assert result.messages[0]["role"] == "user"
    assert result.messages[0]["content"] == "Previous message"
