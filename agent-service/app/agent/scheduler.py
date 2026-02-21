"""APScheduler-based cron job runner for per-tenant scheduled automations.

Each ScheduledJob row in the DB corresponds to one APScheduler cron job.
On app startup, all enabled jobs are loaded and scheduled. After admin
CRUD operations, the scheduler is updated in-place (no restart needed).
"""
import asyncio
import html
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)

_scheduler = None
_session_factory: async_sessionmaker | None = None


# ---------------------------------------------------------------------------
# Job execution
# ---------------------------------------------------------------------------

async def _execute_job(job_id: str) -> None:
    """Called by APScheduler to run a single scheduled job."""
    if _session_factory is None:
        logger.error("Scheduler: session factory not initialised")
        return

    from app.models.scheduled_job import DeliveryChannel, ScheduledJob
    from app.models.tenant import Tenant

    async with _session_factory() as db:
        job = await db.get(ScheduledJob, uuid.UUID(job_id))
        if not job or not job.enabled:
            return

        tenant = await db.get(Tenant, job.tenant_id)
        if not tenant or not tenant.is_active:
            return

        logger.info("Scheduler: running job '%s' for tenant '%s'", job.name, tenant.name)

        # Run a one-shot agent loop (no persistent conversation state)
        from app.agent.loop import run_agent_loop
        try:
            result = await asyncio.wait_for(
                run_agent_loop(tenant=tenant, messages=[], user_message=job.prompt),
                timeout=60,
            )
            response_text = result.response_text or "(no response)"
        except asyncio.TimeoutError:
            response_text = "(scheduled job timed out after 60s)"
            logger.warning("Scheduler: job '%s' timed out", job.name)
        except Exception:
            response_text = "(scheduled job failed — check logs)"
            logger.error("Scheduler: job '%s' failed", job.name, exc_info=True)

        # Deliver result
        if job.delivery_channel == DeliveryChannel.email and job.delivery_target:
            await _deliver_email(tenant, job, response_text)
        elif job.delivery_channel == DeliveryChannel.slack and job.delivery_target:
            await _deliver_slack(job, response_text)

        # Record last run time
        job.last_run_at = datetime.now(timezone.utc)
        await db.commit()


async def _deliver_email(tenant, job, body: str) -> None:
    try:
        from app.config import get_settings
        from app.integrations.email import send_email

        settings = get_settings()
        config = tenant.escalation_config or {}
        api_key = config.get("resend_api_key") or settings.resend_api_key
        if not api_key:
            logger.warning("Scheduler: no Resend API key — cannot send email for job '%s'", job.name)
            return

        from_addr = config.get("from_email") or settings.default_from_email
        html_body = (
            f"<h2>Scheduled Report: {html.escape(job.name)}</h2>"
            f"<pre style='white-space:pre-wrap'>{html.escape(body)}</pre>"
        )
        await send_email(
            api_key=api_key,
            from_addr=from_addr,
            to=job.delivery_target,
            subject=f"[RelayAI] {job.name} — {tenant.name}",
            html_body=html_body,
        )
        logger.info("Scheduler: emailed result for job '%s' to %s", job.name, job.delivery_target)
    except Exception:
        logger.error("Scheduler: email delivery failed for job '%s'", job.name, exc_info=True)


async def _deliver_slack(job, body: str) -> None:
    try:
        import httpx

        payload = {
            "text": f"*Scheduled: {job.name}*\n{body}",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(job.delivery_target, json=payload)
        logger.info("Scheduler: posted result for job '%s' to Slack", job.name)
    except Exception:
        logger.error("Scheduler: Slack delivery failed for job '%s'", job.name, exc_info=True)


# ---------------------------------------------------------------------------
# Scheduler lifecycle
# ---------------------------------------------------------------------------

def _add_apscheduler_job(job) -> None:
    """Register or replace one APScheduler cron job."""
    from apscheduler.triggers.cron import CronTrigger

    try:
        trigger = CronTrigger.from_crontab(job.cron_expression, timezone="UTC")
        _scheduler.add_job(
            _execute_job,
            trigger=trigger,
            args=[str(job.id)],
            id=str(job.id),
            replace_existing=True,
            name=job.name,
        )
        logger.info("Scheduler: registered job '%s' (%s)", job.name, job.cron_expression)
    except Exception:
        logger.error("Scheduler: failed to register job '%s'", job.name, exc_info=True)


async def start_scheduler(session_factory: async_sessionmaker) -> None:
    """Load all enabled jobs from DB and start the APScheduler instance."""
    global _scheduler, _session_factory
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from app.models.scheduled_job import ScheduledJob
    from app.models.tenant import Tenant

    _session_factory = session_factory
    _scheduler = AsyncIOScheduler()

    # Load all enabled jobs for active tenants
    async with session_factory() as db:
        result = await db.execute(
            select(ScheduledJob)
            .join(Tenant, ScheduledJob.tenant_id == Tenant.id)
            .where(ScheduledJob.enabled == True, Tenant.is_active == True)  # noqa: E712
        )
        jobs = result.scalars().all()

    for job in jobs:
        _add_apscheduler_job(job)

    _scheduler.start()
    logger.info("Scheduler: started with %d job(s)", len(jobs))


def stop_scheduler() -> None:
    """Shut down the scheduler gracefully."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler: stopped")
    _scheduler = None


# ---------------------------------------------------------------------------
# Called by admin routes after CRUD operations
# ---------------------------------------------------------------------------

def reload_job(job) -> None:
    """Add or update a job in the running scheduler (called after create/update)."""
    if _scheduler is None:
        return
    if job.enabled:
        _add_apscheduler_job(job)
    else:
        remove_job(str(job.id))


def remove_job(job_id: str) -> None:
    """Remove a job from the scheduler (called after delete or disable)."""
    if _scheduler is None:
        return
    try:
        _scheduler.remove_job(job_id)
        logger.info("Scheduler: removed job %s", job_id)
    except Exception:
        pass  # Job may not be registered (e.g. was disabled)


async def trigger_job_now(job_id: str) -> None:
    """Immediately execute a job outside its schedule (admin test/run-now)."""
    await _execute_job(job_id)
