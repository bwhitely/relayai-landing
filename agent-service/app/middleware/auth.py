import secrets

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import Settings, get_settings

_api_key_header = APIKeyHeader(name="X-API-Key")


async def require_admin(
    api_key: str = Security(_api_key_header),
    settings: Settings = Depends(get_settings),
) -> str:
    if not secrets.compare_digest(api_key, settings.admin_api_key):
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key
