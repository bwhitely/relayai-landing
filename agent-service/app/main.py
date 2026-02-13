import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import close_db, init_db
from app.routers import health, tenants, webhooks
from app.utils.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    init_db(settings.database_url)
    yield
    await close_db()


app = FastAPI(title="RelayAI Agent Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(tenants.router)
app.include_router(webhooks.router)

_static_dir = pathlib.Path(__file__).parent / "static"


@app.get("/admin/dashboard")
async def admin_dashboard():
    return FileResponse(_static_dir / "admin" / "index.html", media_type="text/html")


if _static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")
