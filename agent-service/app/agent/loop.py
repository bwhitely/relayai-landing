import asyncio
import logging
from dataclasses import dataclass, field

from app.agent.prompts import build_system_prompt
from app.agent.tools import execute_tool, get_tools_for_tenant
from app.config import get_settings
from app.integrations.anthropic import call_llm
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

FALLBACK_MESSAGE = (
    "I'm sorry, I'm having a bit of trouble right now. "
    "Let me connect you with someone who can help."
)


@dataclass
class AgentResult:
    response_text: str
    messages: list[dict]
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    model: str = ""
    iterations: int = 0


async def run_agent_loop(
    tenant: Tenant,
    messages: list[dict],
    user_message: str,
) -> AgentResult:
    """Run the core agent loop: message -> LLM -> tool exec -> reply."""
    settings = get_settings()
    system_prompt = build_system_prompt(tenant)
    tools = get_tools_for_tenant(tenant)

    # Append the new user message
    messages = [*messages, {"role": "user", "content": user_message}]

    result = AgentResult(response_text="", messages=messages)

    try:
        response = await asyncio.wait_for(
            _agent_loop(tenant, system_prompt, tools, result, settings.max_agent_iterations),
            timeout=settings.agent_timeout_seconds,
        )
        return response
    except asyncio.TimeoutError:
        logger.warning("Agent loop timed out for tenant=%s", tenant.name)
        result.response_text = FALLBACK_MESSAGE
        result.messages.append({"role": "assistant", "content": FALLBACK_MESSAGE})
        return result
    except Exception:
        logger.error("Agent loop failed for tenant=%s", tenant.name, exc_info=True)
        result.response_text = FALLBACK_MESSAGE
        result.messages.append({"role": "assistant", "content": FALLBACK_MESSAGE})
        return result


async def _agent_loop(
    tenant: Tenant,
    system_prompt: str,
    tools: list[dict],
    result: AgentResult,
    max_iterations: int,
) -> AgentResult:
    for i in range(max_iterations):
        result.iterations = i + 1
        llm_response = await call_llm(
            system_prompt=system_prompt,
            messages=result.messages,
            tools=tools or None,
        )

        result.total_input_tokens += llm_response.input_tokens
        result.total_output_tokens += llm_response.output_tokens
        result.total_cost_usd += llm_response.estimated_cost_usd
        result.model = llm_response.model

        # Append assistant message
        result.messages.append({
            "role": "assistant",
            "content": llm_response.content,
        })

        if llm_response.stop_reason == "end_turn":
            # Extract text from the response
            result.response_text = _extract_text(llm_response.content)
            return result

        if llm_response.stop_reason == "tool_use":
            # Execute each tool call and collect results
            tool_results = []
            for block in llm_response.content:
                if block.get("type") == "tool_use":
                    tool_result = await execute_tool(
                        block["name"], block["input"], tenant
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": tool_result,
                    })

            # Tool results go in a user message (Anthropic API requirement)
            result.messages.append({"role": "user", "content": tool_results})
            continue

    # Max iterations reached — force a text response
    logger.warning("Max iterations (%d) reached for tenant=%s", max_iterations, tenant.name)
    result.response_text = FALLBACK_MESSAGE
    result.messages.append({"role": "assistant", "content": FALLBACK_MESSAGE})
    return result


def _extract_text(content: list[dict]) -> str:
    """Extract text from content blocks."""
    texts = []
    for block in content:
        if block.get("type") == "text":
            texts.append(block["text"])
    return "\n".join(texts) if texts else ""
