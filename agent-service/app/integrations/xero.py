import json
import logging
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

XERO_API_BASE = "https://api.xero.com/api.xro/2.0"
XERO_TOKEN_URL = "https://identity.xero.com/connect/token"


async def _ensure_valid_token(
    creds: dict,
) -> tuple[str, dict | None]:
    """Check token expiry and refresh if needed.

    Args:
        creds: Dict with client_id, client_secret, refresh_token,
            access_token, token_expiry, xero_tenant_id.

    Returns:
        Tuple of (access_token, updated_creds_or_None).
        If token was refreshed, updated_creds contains the new tokens.
        If token was still valid, updated_creds is None.
    """
    token_expiry = creds.get("token_expiry", "")
    if token_expiry:
        expiry = datetime.fromisoformat(token_expiry)
        if expiry > datetime.now(timezone.utc):
            return creds["access_token"], None

    # Token expired or no expiry set — refresh
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            XERO_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": creds["client_id"],
                "client_secret": creds["client_secret"],
                "refresh_token": creds["refresh_token"],
            },
        )
        response.raise_for_status()
        data = response.json()

    # Build updated credentials
    expires_in = data.get("expires_in", 1800)
    new_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    updated_creds = {
        **creds,
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", creds["refresh_token"]),
        "token_expiry": new_expiry.isoformat(),
    }

    logger.info("Xero token refreshed successfully")
    return data["access_token"], updated_creds


def _headers(access_token: str, xero_tenant_id: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Xero-Tenant-Id": xero_tenant_id,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def search_invoices(
    creds: dict,
    contact_name: str | None = None,
    status: str | None = None,
    invoice_number: str | None = None,
) -> tuple[list[dict], dict | None]:
    """Search invoices in Xero.

    Args:
        creds: Xero credentials dict.
        contact_name: Filter by contact name (partial match).
        status: Filter by status (DRAFT, SUBMITTED, AUTHORISED, PAID, VOIDED).
        invoice_number: Filter by invoice number.

    Returns:
        Tuple of (list of invoices, updated_creds_or_None).
    """
    access_token, updated_creds = await _ensure_valid_token(creds)

    # Build WHERE clause
    where_parts = []
    if contact_name:
        safe_name = contact_name.replace('"', '\\"')
        where_parts.append(f'Contact.Name.Contains("{safe_name}")')
    if status:
        where_parts.append(f'Status=="{status}"')
    if invoice_number:
        where_parts.append(f'InvoiceNumber=="{invoice_number}"')

    params: dict = {}
    if where_parts:
        params["where"] = "&&".join(where_parts)
    params["order"] = "Date DESC"

    headers = _headers(access_token, creds["xero_tenant_id"])

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            f"{XERO_API_BASE}/Invoices",
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        data = response.json()

    invoices = [
        {
            "invoice_id": inv["InvoiceID"],
            "invoice_number": inv.get("InvoiceNumber", ""),
            "contact_name": inv.get("Contact", {}).get("Name", ""),
            "status": inv.get("Status", ""),
            "total": inv.get("Total", 0),
            "amount_due": inv.get("AmountDue", 0),
            "amount_paid": inv.get("AmountPaid", 0),
            "date": inv.get("DateString", ""),
            "due_date": inv.get("DueDateString", ""),
            "currency": inv.get("CurrencyCode", "AUD"),
        }
        for inv in data.get("Invoices", [])
    ]

    return invoices, updated_creds


async def get_invoice(
    creds: dict,
    invoice_id: str,
) -> tuple[dict, dict | None]:
    """Get a single invoice with line items.

    Args:
        creds: Xero credentials dict.
        invoice_id: The Xero invoice ID (UUID).

    Returns:
        Tuple of (invoice dict, updated_creds_or_None).
    """
    access_token, updated_creds = await _ensure_valid_token(creds)
    headers = _headers(access_token, creds["xero_tenant_id"])

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            f"{XERO_API_BASE}/Invoices/{invoice_id}",
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

    inv = data.get("Invoices", [{}])[0]
    line_items = [
        {
            "description": li.get("Description", ""),
            "quantity": li.get("Quantity", 0),
            "unit_amount": li.get("UnitAmount", 0),
            "line_amount": li.get("LineAmount", 0),
            "account_code": li.get("AccountCode", ""),
        }
        for li in inv.get("LineItems", [])
    ]

    result = {
        "invoice_id": inv.get("InvoiceID", ""),
        "invoice_number": inv.get("InvoiceNumber", ""),
        "contact_name": inv.get("Contact", {}).get("Name", ""),
        "status": inv.get("Status", ""),
        "total": inv.get("Total", 0),
        "amount_due": inv.get("AmountDue", 0),
        "amount_paid": inv.get("AmountPaid", 0),
        "date": inv.get("DateString", ""),
        "due_date": inv.get("DueDateString", ""),
        "currency": inv.get("CurrencyCode", "AUD"),
        "line_items": line_items,
        "payments": [
            {
                "date": p.get("DateString", ""),
                "amount": p.get("Amount", 0),
                "reference": p.get("Reference", ""),
            }
            for p in inv.get("Payments", [])
        ],
    }

    return result, updated_creds
