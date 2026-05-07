import logging

from django.conf import settings
from twilio.request_validator import RequestValidator
from twilio.rest import Client

from group_text.models import Group, Membership, Message, User

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


def verify_twilio_signature(
    *, url: str, params: dict[str, str], signature: str
) -> bool:
    if not settings.TWILIO_AUTH_TOKEN or not signature:
        return False

    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    return bool(validator.validate(url, params, signature))


def build_group_message_body(*, sender: "User", body: str) -> str:
    return f"{sender.name}: {body.strip()}"


def persist_and_fan_out_group_message(*, group: Group, sender: User, body: str) -> int:
    cleaned_body = body.strip()
    if not cleaned_body:
        return 0

    Message.objects.create(group=group, sender=sender, body=cleaned_body)
    outbound_body = build_group_message_body(sender=sender, body=cleaned_body)
    recipient_phone_numbers = group.members.exclude(
        phone_number=sender.phone_number
    ).values_list("phone_number", flat=True)

    sent_count = 0
    for recipient_phone_number in recipient_phone_numbers:
        sid = send_sms(
            to_phone_number=recipient_phone_number,
            body=outbound_body,
            from_phone_number=group.proxy_number or None,
        )
        if sid is not None:
            sent_count += 1

    return sent_count


def fan_out_inbound_group_message(
    *,
    from_phone_number: str,
    to_proxy_number: str,
    body: str,
) -> int:
    cleaned_body = body.strip()
    if not cleaned_body:
        return 0

    group = Group.objects.filter(proxy_number=to_proxy_number).first()
    if group is None:
        return 0

    membership = (
        Membership.objects.select_related("user")
        .filter(
            group=group,
            user__phone_number=from_phone_number,
        )
        .first()
    )
    if membership is None:
        return 0

    return persist_and_fan_out_group_message(
        group=group,
        sender=membership.user,
        body=cleaned_body,
    )
