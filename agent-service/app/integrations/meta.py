import hashlib
import hmac
import logging

import httpx

logger = logging.getLogger(__name__)

META_GRAPH_API_URL = "https://graph.facebook.com/v21.0"
META_MESSAGE_LIMIT = 2000


def validate_meta_signature(body: bytes, signature: str, app_secret: str) -> bool:
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(
        app_secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


async def send_meta_message(
    recipient_id: str,
    text: str,
    page_id: str,
    access_token: str,
) -> list[dict]:
    url = f"{META_GRAPH_API_URL}/{page_id}/messages"
    headers = {"Authorization": f"Bearer {access_token}"}

    # Split long messages (Meta has 2000-char limit)
    chunks = []
    while len(text) > META_MESSAGE_LIMIT:
        # Try to split at last newline or space within limit
        split_at = text.rfind("\n", 0, META_MESSAGE_LIMIT)
        if split_at == -1:
            split_at = text.rfind(" ", 0, META_MESSAGE_LIMIT)
        if split_at == -1:
            split_at = META_MESSAGE_LIMIT
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()
    if text:
        chunks.append(text)

    results = []
    async with httpx.AsyncClient() as client:
        for chunk in chunks:
            payload = {
                "recipient": {"id": recipient_id},
                "messaging_type": "RESPONSE",
                "message": {"text": chunk},
            }
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            results.append(resp.json())
            logger.info("Sent Meta message to=%s page=%s", recipient_id, page_id)

    return results


def parse_meta_webhook(payload: dict) -> list[dict]:
    obj_type = payload.get("object")
    if obj_type == "page":
        channel = "facebook"
    elif obj_type == "instagram":
        channel = "instagram"
    else:
        return []

    events = []
    for entry in payload.get("entry", []):
        for msg_event in entry.get("messaging", []):
            message = msg_event.get("message", {})
            text = message.get("text")
            if not text:
                continue
            events.append({
                "sender_id": msg_event["sender"]["id"],
                "recipient_id": msg_event["recipient"]["id"],
                "text": text,
                "channel": channel,
            })
    return events
