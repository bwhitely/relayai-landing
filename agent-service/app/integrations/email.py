import logging

import httpx

logger = logging.getLogger(__name__)

RESEND_API_BASE = "https://api.resend.com"


async def send_email(
    api_key: str,
    from_addr: str,
    to: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> dict:
    """Send an email via Resend API.

    Args:
        api_key: Resend API key.
        from_addr: Sender email address.
        to: Recipient email address.
        subject: Email subject line.
        html_body: HTML body content.
        text_body: Optional plain text body.

    Returns:
        Dict with status and email id.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: dict = {
        "from": from_addr,
        "to": [to],
        "subject": subject,
        "html": html_body,
    }
    if text_body:
        payload["text"] = text_body

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{RESEND_API_BASE}/emails",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    logger.info("Email sent via Resend id=%s to=%s", data.get("id"), to)
    return {
        "status": "sent",
        "email_id": data.get("id", ""),
    }
