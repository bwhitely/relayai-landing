import logging

from twilio.request_validator import RequestValidator
from twilio.rest import Client

from app.config import get_settings

logger = logging.getLogger(__name__)


def validate_twilio_signature(url: str, params: dict, signature: str) -> bool:
    settings = get_settings()
    validator = RequestValidator(settings.twilio_auth_token)
    return validator.validate(url, params, signature)


async def send_whatsapp_message(
    to: str,
    body: str,
    from_number: str,
    account_sid: str | None = None,
    auth_token: str | None = None,
) -> str:
    settings = get_settings()
    sid = account_sid or settings.twilio_account_sid
    token = auth_token or settings.twilio_auth_token

    client = Client(sid, token)
    message = client.messages.create(
        body=body,
        from_=f"whatsapp:{from_number}",
        to=to,
    )
    logger.info("Sent WhatsApp message sid=%s to=%s", message.sid, to)
    return message.sid
