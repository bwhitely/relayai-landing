import logging
from dataclasses import dataclass

import anthropic

from app.config import get_settings

logger = logging.getLogger(__name__)

# Pricing per million tokens (Sonnet 4.5)
INPUT_COST_PER_M = 3.00
OUTPUT_COST_PER_M = 15.00


@dataclass
class LLMResponse:
    content: list[dict]
    stop_reason: str
    input_tokens: int
    output_tokens: int
    model: str
    estimated_cost_usd: float


def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * INPUT_COST_PER_M + output_tokens * OUTPUT_COST_PER_M) / 1_000_000


_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    return _client


async def call_llm(
    system_prompt: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    model: str | None = None,
) -> LLMResponse:
    settings = get_settings()
    model = model or settings.default_model

    kwargs: dict = {
        "model": model,
        "max_tokens": 1024,
        "system": system_prompt,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools

    response = await get_client().messages.create(**kwargs)

    # Serialize content blocks to plain dicts
    content = _serialize_content(response.content)

    return LLMResponse(
        content=content,
        stop_reason=response.stop_reason,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        model=model,
        estimated_cost_usd=_estimate_cost(
            response.usage.input_tokens, response.usage.output_tokens
        ),
    )


def _serialize_content(content_blocks) -> list[dict]:
    """Convert Anthropic SDK content blocks to plain dicts for JSONB storage."""
    result = []
    for block in content_blocks:
        if hasattr(block, "model_dump"):
            result.append(block.model_dump())
        elif isinstance(block, dict):
            result.append(block)
        else:
            result.append({"type": "text", "text": str(block)})
    return result
