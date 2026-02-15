import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import require_admin
from app.models import Conversation, Tenant, UsageLog
from app.schemas.tenant import (
    ConversationSummary,
    TenantCreate,
    TenantResponse,
    TenantUpdate,
    UsageResponse,
)
from app.utils.encryption import encrypt

router = APIRouter(prefix="/admin/tenants", dependencies=[Depends(require_admin)])


@router.get("", response_model=list[TenantResponse])
async def list_tenants(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tenant).order_by(Tenant.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=TenantResponse, status_code=201)
async def create_tenant(
    body: TenantCreate,
    db: AsyncSession = Depends(get_db),
):
    tenant = Tenant(
        name=body.name,
        twilio_phone_number=body.twilio_phone_number,
        system_prompt=body.system_prompt,
        tools_config=body.tools_config,
        crm_type=body.crm_type,
        calendar_type=body.calendar_type,
        accounting_type=body.accounting_type,
        meta_page_id=body.meta_page_id,
        escalation_config=body.escalation_config,
        max_conversations_per_month=body.max_conversations_per_month,
        api_key=secrets.token_urlsafe(32),
    )
    # Encrypt sensitive fields if provided
    if body.crm_credentials:
        tenant.crm_credentials = encrypt(body.crm_credentials)
    if body.calendar_credentials:
        tenant.calendar_credentials = encrypt(body.calendar_credentials)
    if body.accounting_credentials:
        tenant.accounting_credentials = encrypt(body.accounting_credentials)
    if body.meta_credentials:
        tenant.meta_credentials = encrypt(body.meta_credentials)
    if body.twilio_account_sid:
        tenant.twilio_account_sid = body.twilio_account_sid
    if body.twilio_auth_token:
        tenant.twilio_auth_token = encrypt(body.twilio_auth_token)

    db.add(tenant)
    await db.flush()
    await db.refresh(tenant)
    return tenant


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: uuid.UUID,
    body: TenantUpdate,
    db: AsyncSession = Depends(get_db),
):
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    update_data = body.model_dump(exclude_unset=True)

    # Encrypt sensitive fields
    if "crm_credentials" in update_data and update_data["crm_credentials"]:
        update_data["crm_credentials"] = encrypt(update_data["crm_credentials"])
    if "calendar_credentials" in update_data and update_data["calendar_credentials"]:
        update_data["calendar_credentials"] = encrypt(update_data["calendar_credentials"])
    if "accounting_credentials" in update_data and update_data["accounting_credentials"]:
        update_data["accounting_credentials"] = encrypt(update_data["accounting_credentials"])
    if "twilio_auth_token" in update_data and update_data["twilio_auth_token"]:
        update_data["twilio_auth_token"] = encrypt(update_data["twilio_auth_token"])
    if "meta_credentials" in update_data and update_data["meta_credentials"]:
        update_data["meta_credentials"] = encrypt(update_data["meta_credentials"])

    for key, value in update_data.items():
        setattr(tenant, key, value)

    await db.flush()
    await db.refresh(tenant)
    return tenant


@router.get("/{tenant_id}/usage", response_model=UsageResponse)
async def get_tenant_usage(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    result = await db.execute(
        select(
            func.coalesce(func.sum(UsageLog.input_tokens), 0).label("total_input"),
            func.coalesce(func.sum(UsageLog.output_tokens), 0).label("total_output"),
            func.coalesce(func.sum(UsageLog.estimated_cost_usd), 0).label("total_cost"),
        ).where(UsageLog.tenant_id == tenant_id)
    )
    row = result.one()

    conv_count = await db.execute(
        select(func.count()).where(Conversation.tenant_id == tenant_id)
    )

    return UsageResponse(
        tenant_id=tenant_id,
        total_input_tokens=row.total_input,
        total_output_tokens=row.total_output,
        total_estimated_cost_usd=float(row.total_cost),
        conversation_count=conv_count.scalar_one(),
    )


@router.get("/{tenant_id}/conversations", response_model=list[ConversationSummary])
async def list_tenant_conversations(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    result = await db.execute(
        select(Conversation)
        .where(Conversation.tenant_id == tenant_id)
        .order_by(Conversation.last_message_at.desc().nullslast())
        .limit(50)
    )
    conversations = result.scalars().all()
    return [
        ConversationSummary(
            id=c.id,
            external_identifier=c.external_identifier,
            channel=c.channel.value,
            status=c.status.value,
            message_count=len(c.messages) if c.messages else 0,
            created_at=c.created_at,
            last_message_at=c.last_message_at,
        )
        for c in conversations
    ]
