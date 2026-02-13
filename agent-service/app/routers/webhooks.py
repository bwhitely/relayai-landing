import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.agent.loop import run_agent_loop
from app.database import get_db
from app.integrations.twilio import send_whatsapp_message, validate_twilio_signature
from app.middleware.rate_limit import check_webhook_rate_limit
from app.models import ChannelType, Conversation, ConversationStatus, Tenant, UsageLog
from app.schemas.webhook import GenericWebhookRequest, GenericWebhookResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", dependencies=[Depends(check_webhook_rate_limit)])


async def _get_or_create_conversation(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    external_identifier: str,
    channel: ChannelType,
) -> Conversation:
    result = await db.execute(
        select(Conversation).where(
            Conversation.tenant_id == tenant_id,
            Conversation.external_identifier == external_identifier,
            Conversation.status == ConversationStatus.active,
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation:
        return conversation

    conversation = Conversation(
        tenant_id=tenant_id,
        external_identifier=external_identifier,
        channel=channel,
        messages=[],
        status=ConversationStatus.active,
    )
    db.add(conversation)
    await db.flush()
    return conversation


async def _log_usage(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    conversation_id: uuid.UUID,
    input_tokens: int,
    output_tokens: int,
    model: str,
    cost: float,
) -> None:
    log = UsageLog(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model=model,
        estimated_cost_usd=cost,
    )
    db.add(log)


@router.post("/twilio/whatsapp")
async def twilio_whatsapp_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    params = dict(form)

    # Validate Twilio signature
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    if not validate_twilio_signature(url, params, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    # Extract message fields
    to_number = params.get("To", "").replace("whatsapp:", "")
    from_number = params.get("From", "")
    body = params.get("Body", "")

    if not body:
        return {"status": "ignored", "reason": "empty message"}

    # Look up tenant by phone number
    result = await db.execute(
        select(Tenant).where(
            Tenant.twilio_phone_number == to_number,
            Tenant.is_active == True,
        )
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        logger.warning("No tenant found for number=%s", to_number)
        raise HTTPException(status_code=404, detail="No tenant for this number")

    # Get or create conversation
    conversation = await _get_or_create_conversation(
        db, tenant.id, from_number, ChannelType.whatsapp
    )

    # Run agent loop
    agent_result = await run_agent_loop(tenant, conversation.messages, body)

    # Update conversation
    conversation.messages = agent_result.messages
    flag_modified(conversation, "messages")
    conversation.last_message_at = datetime.now(timezone.utc)

    # Log usage
    await _log_usage(
        db,
        tenant.id,
        conversation.id,
        agent_result.total_input_tokens,
        agent_result.total_output_tokens,
        agent_result.model,
        agent_result.total_cost_usd,
    )

    # Send reply via Twilio
    await send_whatsapp_message(
        to=from_number,
        body=agent_result.response_text,
        from_number=to_number,
    )

    return {"status": "ok"}


@router.post("/generic/{tenant_id}", response_model=GenericWebhookResponse)
async def generic_webhook(
    tenant_id: uuid.UUID,
    body: GenericWebhookRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Authenticate with tenant API key
    api_key = request.headers.get("X-API-Key", "")
    tenant = await db.get(Tenant, tenant_id)
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if not tenant.api_key or tenant.api_key != api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")

    # Get or create conversation
    conversation = await _get_or_create_conversation(
        db, tenant.id, body.sender_id, ChannelType.web
    )

    # Run agent loop
    agent_result = await run_agent_loop(tenant, conversation.messages, body.message)

    # Update conversation
    conversation.messages = agent_result.messages
    flag_modified(conversation, "messages")
    conversation.last_message_at = datetime.now(timezone.utc)

    # Log usage
    await _log_usage(
        db,
        tenant.id,
        conversation.id,
        agent_result.total_input_tokens,
        agent_result.total_output_tokens,
        agent_result.model,
        agent_result.total_cost_usd,
    )

    return GenericWebhookResponse(
        response=agent_result.response_text,
        conversation_id=str(conversation.id),
    )
