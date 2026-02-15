from pydantic import BaseModel, Field


class GenericWebhookRequest(BaseModel):
    sender_id: str = Field(..., max_length=128)
    message: str = Field(..., max_length=4000)


class ToolCallInfo(BaseModel):
    tool: str
    input: dict
    result: dict | str
    duration_ms: int | None = None


class GenericWebhookResponse(BaseModel):
    response: str
    conversation_id: str
    tool_calls: list[ToolCallInfo] | None = None
    iterations: int | None = None
