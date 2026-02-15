"""Export a tenant from the local DB as a curl command for recreating on production.

Usage:
    source .venv/bin/activate
    python scripts/export_tenant.py <tenant_id>

Reads from your local .env for DATABASE_URL and FERNET_KEY,
decrypts all credentials, and prints a curl command you can
run against your production API.
"""

import asyncio
import json
import sys

from app.config import get_settings
from app.database import init_db, get_session_factory
from app.models.tenant import Tenant
from app.utils.encryption import decrypt


async def export_tenant(tenant_id: str) -> None:
    settings = get_settings()
    init_db(settings.database_url)
    factory = get_session_factory()

    async with factory() as db:
        tenant = await db.get(Tenant, tenant_id)
        if not tenant:
            print(f"Tenant {tenant_id} not found")
            sys.exit(1)

    # Build the payload, decrypting any encrypted fields
    payload = {
        "name": tenant.name,
        "max_conversations_per_month": tenant.max_conversations_per_month,
        "crm_type": tenant.crm_type.value if tenant.crm_type else "none",
        "calendar_type": tenant.calendar_type.value if tenant.calendar_type else "none",
        "accounting_type": tenant.accounting_type.value if tenant.accounting_type else "none",
    }

    if tenant.system_prompt:
        payload["system_prompt"] = tenant.system_prompt
    if tenant.tools_config:
        payload["tools_config"] = tenant.tools_config
    if tenant.twilio_phone_number:
        payload["twilio_phone_number"] = tenant.twilio_phone_number
    if tenant.escalation_config:
        payload["escalation_config"] = tenant.escalation_config
    if tenant.meta_page_id:
        payload["meta_page_id"] = tenant.meta_page_id

    # Decrypt encrypted fields
    if tenant.crm_credentials:
        try:
            payload["crm_credentials"] = decrypt(tenant.crm_credentials)
        except Exception:
            payload["crm_credentials"] = tenant.crm_credentials
            print("WARNING: Could not decrypt crm_credentials, using raw value")

    if tenant.calendar_credentials:
        try:
            payload["calendar_credentials"] = decrypt(tenant.calendar_credentials)
        except Exception:
            payload["calendar_credentials"] = tenant.calendar_credentials
            print("WARNING: Could not decrypt calendar_credentials, using raw value")

    if tenant.accounting_credentials:
        try:
            payload["accounting_credentials"] = decrypt(tenant.accounting_credentials)
        except Exception:
            payload["accounting_credentials"] = tenant.accounting_credentials
            print("WARNING: Could not decrypt accounting_credentials, using raw value")

    if tenant.meta_credentials:
        try:
            payload["meta_credentials"] = decrypt(tenant.meta_credentials)
        except Exception:
            payload["meta_credentials"] = tenant.meta_credentials
            print("WARNING: Could not decrypt meta_credentials, using raw value")

    if tenant.twilio_account_sid:
        payload["twilio_account_sid"] = tenant.twilio_account_sid

    if tenant.twilio_auth_token:
        try:
            payload["twilio_auth_token"] = decrypt(tenant.twilio_auth_token)
        except Exception:
            payload["twilio_auth_token"] = tenant.twilio_auth_token
            print("WARNING: Could not decrypt twilio_auth_token, using raw value")

    payload_json = json.dumps(payload, indent=2)

    print("\n" + "=" * 60)
    print("TENANT EXPORT")
    print("=" * 60)
    print(f"Name: {tenant.name}")
    print(f"Local ID: {tenant.id}")
    print(f"Local API Key: {tenant.api_key}")
    print("=" * 60)

    print("\nPayload (for review):\n")
    print(payload_json)

    print("\n" + "=" * 60)
    print("CURL COMMAND (run against production)")
    print("=" * 60)

    # Escape single quotes in JSON for shell
    escaped = payload_json.replace("'", "'\\''")

    print(f"""
curl -X POST https://YOUR_PROD_URL/admin/tenants \\
  -H "X-API-Key: YOUR_PROD_ADMIN_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{escaped}'
""")

    print("NOTE: The new tenant will get a different ID and API key.")
    print("Update DEMO_CONFIG in landing-page/index.html with the new values.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <tenant_id>")
        sys.exit(1)
    asyncio.run(export_tenant(sys.argv[1]))
