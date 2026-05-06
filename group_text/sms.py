import logging

from django.conf import settings
from twilio.rest import Client

from group_text.models import Group, User

logger = logging.getLogger(__name__)


def get_twilio_client() -> Client | None:
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        return None

    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def send_sms(
    *,
    to_phone_number: str,
    body: str,
    from_phone_number: str | None = None,
) -> str | None:
    client = get_twilio_client()
    sender = from_phone_number or settings.TWILIO_PHONE_NUMBER

    if client is None or not sender:
        return None

    try:
        message = client.messages.create(body=body, from_=sender, to=to_phone_number)
    except Exception:
        logger.exception("Failed to send outbound SMS", extra={"to": to_phone_number})
        return None

    return str(message.sid)


def build_welcome_sms_body(*, user: "User", group: "Group") -> str:
    return (
        f"Welcome to {group.name}, {user.name}! "
        "You have joined the group and will receive new messages here."
    )


def send_welcome_sms(*, user: "User", group: "Group") -> str | None:
    return send_sms(
        to_phone_number=user.phone_number,
        body=build_welcome_sms_body(user=user, group=group),
        from_phone_number=group.proxy_number or None,
    )
