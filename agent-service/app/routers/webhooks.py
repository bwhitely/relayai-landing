import asyncio
import json
import logging
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.agent.loop import FALLBACK_MESSAGE, AgentResult, run_agent_loop
from app.database import get_db, get_session_factory
from app.integrations.meta import parse_meta_webhook, send_meta_message, validate_meta_signature
from app.integrations.twilio import send_sms_message, send_whatsapp_message, validate_twilio_signature
from app.middleware.rate_limit import check_webhook_rate_limit
from app.models import ChannelType, Conversation, ConversationStatus, Tenant, UsageLog
from app.schemas.webhook import GenericWebhookRequest, GenericWebhookResponse, ToolCallInfo
from app.utils.encryption import decrypt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", dependencies=[Depends(check_webhook_rate_limit)])


async def _check_conversation_limit(
    db: AsyncSession,
    tenant: Tenant,
) -> bool:
    """Return True if tenant is within their monthly conversation limit."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    from sqlalchemy import func as sqlfunc
    count_result = await db.execute(
        select(sqlfunc.count()).where(
            Conversation.tenant_id == tenant.id,
            Conversation.created_at >= month_start,
        )
    )
    count = count_result.scalar_one()
    return count < tenant.max_conversations_per_month


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

    # Check monthly conversation limit
    if not await _check_conversation_limit(db, tenant):
        logger.warning("Tenant %s exceeded monthly conversation limit", tenant.name)
        return {"status": "rejected", "reason": "monthly limit reached"}

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


@router.post("/twilio/sms")
async def twilio_sms_webhook(
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

    # Extract message fields (SMS has no 'whatsapp:' prefix)
    to_number = params.get("To", "")
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

    # Check monthly conversation limit
    if not await _check_conversation_limit(db, tenant):
        logger.warning("Tenant %s exceeded monthly conversation limit", tenant.name)
        return {"status": "rejected", "reason": "monthly limit reached"}

    # Get or create conversation
    conversation = await _get_or_create_conversation(
        db, tenant.id, from_number, ChannelType.sms
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

    # Send reply via Twilio SMS
    await send_sms_message(
        to=from_number,
        body=agent_result.response_text,
        from_number=to_number,
    )

    return {"status": "ok"}


def _extract_tool_calls(messages: list[dict]) -> list[ToolCallInfo]:
    """Extract tool_use/tool_result pairs from agent conversation messages."""
    tool_calls = []
    pending: dict[str, dict] = {}
    for msg in messages:
        if msg.get("role") == "assistant":
            for block in msg.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    pending[block["id"]] = {"tool": block["name"], "input": block.get("input", {})}
        elif msg.get("role") == "user":
            for block in msg.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    tid = block.get("tool_use_id")
                    if tid in pending:
                        info = pending.pop(tid)
                        raw = block.get("content", "")
                        try:
                            result = json.loads(raw)
                        except (json.JSONDecodeError, TypeError):
                            result = raw
                        tool_calls.append(ToolCallInfo(tool=info["tool"], input=info["input"], result=result))
    return tool_calls


@router.post("/generic/{tenant_id}", response_model=GenericWebhookResponse)
async def generic_webhook(
    tenant_id: uuid.UUID,
    body: GenericWebhookRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    include_tool_calls: bool = Query(False),
):
    # Authenticate with tenant API key
    api_key = request.headers.get("X-API-Key", "")
    tenant = await db.get(Tenant, tenant_id)
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if not tenant.api_key or not secrets.compare_digest(tenant.api_key, api_key):
        raise HTTPException(status_code=403, detail="Invalid API key")

    # Check monthly conversation limit
    if not await _check_conversation_limit(db, tenant):
        raise HTTPException(status_code=429, detail="Monthly conversation limit reached")

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

    tool_calls = _extract_tool_calls(agent_result.messages) if include_tool_calls else None

    return GenericWebhookResponse(
        response=agent_result.response_text,
        conversation_id=str(conversation.id),
        tool_calls=tool_calls if include_tool_calls else None,
        iterations=agent_result.iterations if include_tool_calls else None,
    )


@router.get("/meta")
async def meta_verify(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode != "subscribe" or not token or not challenge:
        raise HTTPException(status_code=403, detail="Invalid verification request")

    # Check all tenants with meta_credentials for a matching verify_token
    result = await db.execute(
        select(Tenant).where(
            Tenant.meta_credentials.isnot(None),
            Tenant.is_active == True,
        )
    )
    tenants = result.scalars().all()
    for tenant in tenants:
        try:
            creds = json.loads(decrypt(tenant.meta_credentials))
            if creds.get("verify_token") == token:
                return PlainTextResponse(content=challenge)
        except Exception:
            continue

    raise HTTPException(status_code=403, detail="Verify token not recognized")


@router.post("/meta")
async def meta_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    raw_body = await request.body()
    payload = json.loads(raw_body)

    # Extract page/instagram ID from first entry
    entries = payload.get("entry", [])
    if not entries:
        return {"status": "ok"}

    page_id = str(entries[0].get("id", ""))
    if not page_id:
        return {"status": "ok"}

    # Look up tenant by meta_page_id
    result = await db.execute(
        select(Tenant).where(
            Tenant.meta_page_id == page_id,
            Tenant.is_active == True,
        )
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        logger.warning("No tenant found for meta page_id=%s", page_id)
        return {"status": "ok"}

    # Decrypt credentials and validate signature
    try:
        creds = json.loads(decrypt(tenant.meta_credentials))
    except Exception:
        logger.error("Failed to decrypt meta_credentials for tenant=%s", tenant.id)
        return {"status": "ok"}

    signature = request.headers.get("X-Hub-Signature-256", "")
    if not validate_meta_signature(raw_body, signature, creds["app_secret"]):
        logger.warning("Invalid Meta signature for tenant=%s", tenant.id)
        return {"status": "ok"}

    # Parse messaging events
    events = parse_meta_webhook(payload)
    access_token = creds["page_access_token"]

    # Kick off background tasks — return 200 immediately (Meta requires <5s)
    for event in events:
        channel = ChannelType.facebook if event["channel"] == "facebook" else ChannelType.instagram
        asyncio.create_task(
            _process_meta_message(
                tenant_id=tenant.id,
                sender_id=event["sender_id"],
                message_text=event["text"],
                channel=channel,
                page_id=page_id,
                access_token=access_token,
            )
        )

    return {"status": "ok"}


async def _process_meta_message(
    tenant_id: uuid.UUID,
    sender_id: str,
    message_text: str,
    channel: ChannelType,
    page_id: str,
    access_token: str,
) -> None:
    session_factory = get_session_factory()
    agent_result = AgentResult(
        response_text=FALLBACK_MESSAGE, messages=[], model="", iterations=0
    )

    try:
        async with session_factory() as db:
            try:
                tenant = await db.get(Tenant, tenant_id)
                conversation = await _get_or_create_conversation(
                    db, tenant.id, sender_id, channel
                )

                agent_result = await run_agent_loop(
                    tenant, conversation.messages, message_text
                )

                conversation.messages = agent_result.messages
                flag_modified(conversation, "messages")
                conversation.last_message_at = datetime.now(timezone.utc)

                await _log_usage(
                    db,
                    tenant.id,
                    conversation.id,
                    agent_result.total_input_tokens,
                    agent_result.total_output_tokens,
                    agent_result.model,
                    agent_result.total_cost_usd,
                )
                await db.commit()
            except Exception:
                await db.rollback()
                logger.exception("Meta message processing failed for tenant=%s", tenant_id)
    except Exception:
        logger.exception("Failed to create DB session for Meta message processing")

    # Send reply outside the DB session
    try:
        await send_meta_message(sender_id, agent_result.response_text, page_id, access_token)
    except Exception:
        logger.exception("Failed to send Meta reply to=%s", sender_id)
