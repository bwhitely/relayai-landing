"""Admin CRUD endpoints for per-tenant scheduled automations."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import require_admin
from app.models import ScheduledJob, Tenant
from app.models.scheduled_job import DeliveryChannel

router = APIRouter(
    prefix="/admin/tenants/{tenant_id}/scheduled-jobs",
    dependencies=[Depends(require_admin)],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ScheduledJobCreate(BaseModel):
    name: str
    cron_expression: str
    prompt: str
    delivery_channel: DeliveryChannel = DeliveryChannel.none
    delivery_target: str | None = None
    enabled: bool = True

    @field_validator("cron_expression")
    @classmethod
    def validate_cron(cls, v: str) -> str:
        from apscheduler.triggers.cron import CronTrigger
        try:
            CronTrigger.from_crontab(v, timezone="UTC")
        except Exception as e:
            raise ValueError(f"Invalid cron expression: {e}") from e
        return v


class ScheduledJobUpdate(BaseModel):
    name: str | None = None
    cron_expression: str | None = None
    prompt: str | None = None
    delivery_channel: DeliveryChannel | None = None
    delivery_target: str | None = None
    enabled: bool | None = None

    @field_validator("cron_expression")
    @classmethod
    def validate_cron(cls, v: str | None) -> str | None:
        if v is None:
            return v
        from apscheduler.triggers.cron import CronTrigger
        try:
            CronTrigger.from_crontab(v, timezone="UTC")
        except Exception as e:
            raise ValueError(f"Invalid cron expression: {e}") from e
        return v


class ScheduledJobResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    cron_expression: str
    prompt: str
    delivery_channel: DeliveryChannel
    delivery_target: str | None
    enabled: bool
    last_run_at: str | None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_obj(cls, j: ScheduledJob) -> "ScheduledJobResponse":
        return cls(
            id=j.id,
            tenant_id=j.tenant_id,
            name=j.name,
            cron_expression=j.cron_expression,
            prompt=j.prompt,
            delivery_channel=j.delivery_channel,
            delivery_target=j.delivery_target,
            enabled=j.enabled,
            last_run_at=j.last_run_at.isoformat() if j.last_run_at else None,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_tenant(tenant_id: uuid.UUID, db: AsyncSession) -> Tenant:
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ScheduledJobResponse])
async def list_scheduled_jobs(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await _get_tenant(tenant_id, db)
    result = await db.execute(
        select(ScheduledJob)
        .where(ScheduledJob.tenant_id == tenant_id)
        .order_by(ScheduledJob.created_at)
    )
    return [ScheduledJobResponse.from_orm_obj(j) for j in result.scalars().all()]


@router.post("", response_model=ScheduledJobResponse, status_code=201)
async def create_scheduled_job(
    tenant_id: uuid.UUID,
    body: ScheduledJobCreate,
    db: AsyncSession = Depends(get_db),
):
    await _get_tenant(tenant_id, db)

    job = ScheduledJob(
        tenant_id=tenant_id,
        name=body.name,
        cron_expression=body.cron_expression,
        prompt=body.prompt,
        delivery_channel=body.delivery_channel,
        delivery_target=body.delivery_target,
        enabled=body.enabled,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)

    # Register with the live scheduler
    from app.agent.scheduler import reload_job
    reload_job(job)

    return ScheduledJobResponse.from_orm_obj(job)


@router.get("/{job_id}", response_model=ScheduledJobResponse)
async def get_scheduled_job(
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await _get_tenant(tenant_id, db)
    job = await db.get(ScheduledJob, job_id)
    if not job or job.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return ScheduledJobResponse.from_orm_obj(job)


@router.put("/{job_id}", response_model=ScheduledJobResponse)
async def update_scheduled_job(
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    body: ScheduledJobUpdate,
    db: AsyncSession = Depends(get_db),
):
    await _get_tenant(tenant_id, db)
    job = await db.get(ScheduledJob, job_id)
    if not job or job.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Job not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(job, field, value)

    await db.flush()
    await db.refresh(job)

    from app.agent.scheduler import reload_job
    reload_job(job)

    return ScheduledJobResponse.from_orm_obj(job)


@router.delete("/{job_id}", status_code=204)
async def delete_scheduled_job(
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await _get_tenant(tenant_id, db)
    job = await db.get(ScheduledJob, job_id)
    if not job or job.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Job not found")

    from app.agent.scheduler import remove_job
    remove_job(str(job_id))

    await db.delete(job)


@router.post("/{job_id}/run", status_code=202)
async def run_job_now(
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Trigger immediate execution of a scheduled job (for testing)."""
    await _get_tenant(tenant_id, db)
    job = await db.get(ScheduledJob, job_id)
    if not job or job.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Job not found")

    import asyncio
    from app.agent.scheduler import trigger_job_now
    asyncio.create_task(trigger_job_now(str(job_id)))

    return {"status": "triggered", "job_id": str(job_id)}
