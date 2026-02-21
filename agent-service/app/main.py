import logging
import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import close_db, init_db
from app.routers import client, health, scheduled_jobs, tenants, webhooks
from app.utils.logging import setup_logging

logger = logging.getLogger(__name__)


def _run_migrations() -> None:
    """Run alembic migrations programmatically (uses DATABASE_URL from env)."""
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(
        str(pathlib.Path(__file__).parent.parent / "alembic.ini")
    )
    alembic_cfg.set_main_option(
        "script_location",
        str(pathlib.Path(__file__).parent.parent / "alembic"),
    )
    command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    try:
        _run_migrations()
        logger.info("Database migrations complete")
    except Exception:
        logger.exception("Migration failed — starting anyway")
    init_db(settings.database_url)
    from app.agent.scheduler import start_scheduler, stop_scheduler
    from app.database import get_session_factory
    try:
        await start_scheduler(get_session_factory())
        logger.info("Scheduler started")
    except Exception:
        logger.exception("Scheduler failed to start — running without scheduled jobs")
    yield
    stop_scheduler()
    await close_db()


app = FastAPI(title="RelayAI Agent Service", lifespan=lifespan)

_cors_origins = get_settings().cors_origins.split(",") if get_settings().cors_origins else []
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
)

app.include_router(health.router)
app.include_router(tenants.router)
app.include_router(webhooks.router)
app.include_router(scheduled_jobs.router)
app.include_router(client.router)

_static_dir = pathlib.Path(__file__).parent / "static"


@app.get("/admin/dashboard")
async def admin_dashboard():
    return FileResponse(_static_dir / "admin" / "index.html", media_type="text/html")


if _static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

_client_static = _static_dir / "client"
if _client_static.is_dir():
    app.mount("/client", StaticFiles(directory=_client_static, html=True), name="client-static")
