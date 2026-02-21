import re
import uuid as uuid_lib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Conversation, ConversationStatus, Tenant

router = APIRouter(prefix="/client")


async def _get_client_tenant(
    request: Request, db: AsyncSession = Depends(get_db)
) -> Tenant:
    api_key = request.headers.get("X-API-Key", "")
    if not api_key:
        raise HTTPException(status_code=403)
    result = await db.execute(
        select(Tenant).where(Tenant.api_key == api_key, Tenant.is_active == True)  # noqa: E712
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=403)
    return tenant


def _anonymise(identifier: str, channel: str) -> str:
    """Return a privacy-safe label for an external conversation identifier."""
    # Strip Twilio WhatsApp prefix if present
    clean = identifier.removeprefix("whatsapp:")

    # Phone number (E.164): +XXXXXXXX
    if re.match(r"^\+\d{6,}$", clean):
        suffix = clean[-4:]
        label = {
            "whatsapp": "WhatsApp",
            "sms": "SMS",
            "facebook": "Messenger",
            "instagram": "Instagram",
        }.get(channel, channel.capitalize())
        return f"{label} ••••{suffix}"

    # Email address
    if "@" in identifier:
        local, _, domain = identifier.partition("@")
        masked = (local[0] + "•••") if local else "•••"
        return f"{masked}@{domain}"

    # UUID — treat as web/generic session
    try:
        uuid_lib.UUID(identifier)
        return f"Web user {identifier[:4]}…"
    except ValueError:
        pass

    # Fallback: truncate
    return f"User {identifier[:4]}…" if len(identifier) > 4 else identifier


@router.get("/me")
async def client_me(tenant: Tenant = Depends(_get_client_tenant)):
    return {
        "name": tenant.name,
        "is_active": tenant.is_active,
        "conversations_limit": tenant.max_conversations_per_month,
    }


@router.get("/stats")
async def client_stats(
    tenant: Tenant = Depends(_get_client_tenant),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_start.month == 1:
        last_month_start = month_start.replace(year=month_start.year - 1, month=12)
    else:
        last_month_start = month_start.replace(month=month_start.month - 1)
    thirty_days_ago = now - timedelta(days=30)

    this_month = await db.scalar(
        select(func.count()).where(
            Conversation.tenant_id == tenant.id,
            Conversation.created_at >= month_start,
        )
    ) or 0

    last_month = await db.scalar(
        select(func.count()).where(
            Conversation.tenant_id == tenant.id,
            Conversation.created_at >= last_month_start,
            Conversation.created_at < month_start,
        )
    ) or 0

    escalations = await db.scalar(
        select(func.count()).where(
            Conversation.tenant_id == tenant.id,
            Conversation.created_at >= month_start,
            Conversation.status == ConversationStatus.escalated,
        )
    ) or 0

    self_service_rate = (
        round((this_month - escalations) / this_month * 100, 1) if this_month > 0 else 0.0
    )

    # Channel breakdown — this month, ordered by volume
    chan_result = await db.execute(
        select(Conversation.channel, func.count().label("cnt"))
        .where(
            Conversation.tenant_id == tenant.id,
            Conversation.created_at >= month_start,
        )
        .group_by(Conversation.channel)
        .order_by(func.count().desc())
    )
    chan_rows = chan_result.all()
    total_chan = sum(r.cnt for r in chan_rows)
    channel_breakdown = [
        {
            "channel": r.channel.value,
            "count": r.cnt,
            "percentage": round(r.cnt / total_chan * 100, 1) if total_chan else 0.0,
        }
        for r in chan_rows
    ]

    # Daily volume — last 30 days
    day_result = await db.execute(
        select(
            func.date(Conversation.created_at).label("day"),
            func.count().label("cnt"),
        )
        .where(
            Conversation.tenant_id == tenant.id,
            Conversation.created_at >= thirty_days_ago,
        )
        .group_by("day")
        .order_by("day")
    )
    daily_volume = [{"date": str(r.day), "count": r.cnt} for r in day_result.all()]

    # Avg messages per conversation — last 50 conversations
    msgs_result = await db.execute(
        select(Conversation.messages)
        .where(Conversation.tenant_id == tenant.id)
        .order_by(Conversation.last_message_at.desc().nullslast())
        .limit(50)
    )
    all_messages = msgs_result.scalars().all()
    avg_messages = 0.0
    if all_messages:
        total_msgs = sum(len(m) for m in all_messages if m)
        avg_messages = round(total_msgs / len(all_messages), 1)

    return {
        "conversations_this_month": this_month,
        "conversations_last_month": last_month,
        "escalation_count_this_month": escalations,
        "self_service_rate": self_service_rate,
        "channel_breakdown": channel_breakdown,
        "daily_volume": daily_volume,
        "avg_messages_per_conversation": avg_messages,
        "conversations_used": this_month,
        "conversations_limit": tenant.max_conversations_per_month,
    }


@router.get("/conversations")
async def client_conversations(
    tenant: Tenant = Depends(_get_client_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.tenant_id == tenant.id)
        .order_by(Conversation.last_message_at.desc().nullslast())
        .limit(20)
    )
    conversations = result.scalars().all()
    return [
        {
            "channel": c.channel.value,
            "identifier": _anonymise(c.external_identifier, c.channel.value),
            "status": c.status.value,
            "message_count": len(c.messages) if c.messages else 0,
            "last_activity": (
                c.last_message_at.isoformat()
                if c.last_message_at
                else c.created_at.isoformat()
            ),
        }
        for c in conversations
    ]
