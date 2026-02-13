import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.tenant import CRMType


class TenantCreate(BaseModel):
    name: str
    twilio_phone_number: str | None = None
    system_prompt: str | None = None
    tools_config: dict | None = None
    crm_type: CRMType = CRMType.none
    crm_credentials: str | None = None
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    escalation_config: dict | None = None
    max_conversations_per_month: int = 100


class TenantUpdate(BaseModel):
    name: str | None = None
    twilio_phone_number: str | None = None
    system_prompt: str | None = None
    tools_config: dict | None = None
    crm_type: CRMType | None = None
    crm_credentials: str | None = None
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    escalation_config: dict | None = None
    max_conversations_per_month: int | None = None
    is_active: bool | None = None


class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    twilio_phone_number: str | None
    system_prompt: str | None
    tools_config: dict | None
    crm_type: CRMType
    escalation_config: dict | None
    max_conversations_per_month: int
    is_active: bool
    api_key: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UsageResponse(BaseModel):
    tenant_id: uuid.UUID
    total_input_tokens: int
    total_output_tokens: int
    total_estimated_cost_usd: float
    conversation_count: int


class ConversationSummary(BaseModel):
    id: uuid.UUID
    external_identifier: str
    channel: str
    status: str
    message_count: int
    created_at: datetime
    last_message_at: datetime | None

    model_config = {"from_attributes": True}
