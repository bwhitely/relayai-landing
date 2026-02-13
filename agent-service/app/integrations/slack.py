import logging

import httpx

logger = logging.getLogger(__name__)


async def send_slack_message(
    webhook_url: str,
    text: str,
    blocks: list[dict] | None = None,
) -> dict:
    """Send a message to a Slack channel via Incoming Webhook.

    Args:
        webhook_url: Slack Incoming Webhook URL.
        text: Fallback text (shown in notifications).
        blocks: Optional Block Kit blocks for rich formatting.

    Returns:
        Dict with status.
    """
    payload: dict = {"text": text}
    if blocks:
        payload["blocks"] = blocks

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(webhook_url, json=payload)
        response.raise_for_status()

    logger.info("Slack message sent successfully")
    return {"status": "sent"}


async def send_escalation_notification(
    webhook_url: str,
    tenant_name: str,
    reason: str,
    summary: str,
    sender_id: str,
) -> dict:
    """Send a formatted escalation notification to Slack.

    Args:
        webhook_url: Slack Incoming Webhook URL.
        tenant_name: Name of the tenant/business.
        reason: Why the conversation is being escalated.
        summary: Brief conversation summary.
        sender_id: The customer's identifier (phone, email, etc.).

    Returns:
        Dict with status.
    """
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Escalation Required",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Business:*\n{tenant_name}"},
                {"type": "mrkdwn", "text": f"*Customer:*\n{sender_id}"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Reason:*\n{reason}",
            },
        },
    ]

    if summary:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Conversation Summary:*\n{summary}",
            },
        })

    fallback_text = f"Escalation from {tenant_name}: {reason}"
    return await send_slack_message(webhook_url, fallback_text, blocks)
