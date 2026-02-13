from pydantic import BaseModel


class GenericWebhookRequest(BaseModel):
    sender_id: str
    message: str


class GenericWebhookResponse(BaseModel):
    response: str
    conversation_id: str
