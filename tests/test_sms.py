from unittest.mock import Mock, patch

import pytest
from django.test import override_settings

from group_text.models import Group, Membership
from group_text.sms import (
    build_group_message_body,
    build_welcome_sms_body,
    fan_out_inbound_group_message,
    send_sms,
    send_welcome_sms,
    verify_twilio_signature,
)


@pytest.mark.django_db
class TestSMSHelpers:
    @override_settings(
        TWILIO_ACCOUNT_SID="AC123",
        TWILIO_AUTH_TOKEN="secret",
        TWILIO_PHONE_NUMBER="+15550009999",
    )
    @patch("group_text.sms.Client")
    def test_send_sms_uses_twilio_client_and_returns_sid(self, mock_client_class):
        mock_message = Mock(sid="SM123")
        mock_client = Mock()
        mock_client.messages.create.return_value = mock_message
        mock_client_class.return_value = mock_client

        message_sid = send_sms(
            to_phone_number="+15550000001",
            body="hello world",
        )

        assert message_sid == "SM123"
        mock_client_class.assert_called_once_with("AC123", "secret")
        mock_client.messages.create.assert_called_once_with(
            body="hello world",
            from_="+15550009999",
            to="+15550000001",
        )

    @override_settings(
        TWILIO_ACCOUNT_SID="",
        TWILIO_AUTH_TOKEN="",
        TWILIO_PHONE_NUMBER="",
    )
    def test_send_sms_is_noop_without_twilio_configuration(self):
        message_sid = send_sms(
            to_phone_number="+15550000001",
            body="hello world",
        )

        assert message_sid is None

    @override_settings(
        TWILIO_ACCOUNT_SID="AC123",
        TWILIO_AUTH_TOKEN="secret",
        TWILIO_PHONE_NUMBER="+15550009999",
    )
    @patch("group_text.sms.send_sms")
    def test_send_welcome_sms_uses_group_proxy_number_when_present(
        self, mock_send_sms, user, group
    ):
        group.proxy_number = "+15550008888"

        send_welcome_sms(user=user, group=group)

        mock_send_sms.assert_called_once_with(
            to_phone_number=user.phone_number,
            body=build_welcome_sms_body(user=user, group=group),
            from_phone_number="+15550008888",
        )

    @override_settings(TWILIO_AUTH_TOKEN="secret")
    @patch("group_text.sms.RequestValidator")
    def test_verify_twilio_signature_uses_request_validator(self, mock_validator_class):
        mock_validator = Mock()
        mock_validator.validate.return_value = True
        mock_validator_class.return_value = mock_validator

        is_valid = verify_twilio_signature(
            url="https://example.com/webhooks/twilio/sms/",
            params={"From": "+15550000001", "Body": "Hello"},
            signature="valid-signature",
        )

        assert is_valid is True
        mock_validator_class.assert_called_once_with("secret")
        mock_validator.validate.assert_called_once_with(
            "https://example.com/webhooks/twilio/sms/",
            {"From": "+15550000001", "Body": "Hello"},
            "valid-signature",
        )

    @override_settings(TWILIO_AUTH_TOKEN="")
    def test_verify_twilio_signature_rejects_without_token(self):
        is_valid = verify_twilio_signature(
            url="https://example.com/webhooks/twilio/sms/",
            params={"From": "+15550000001"},
            signature="whatever",
        )

        assert is_valid is False

    @patch("group_text.sms.send_sms")
    def test_fan_out_inbound_group_message_sends_to_other_members_only(
        self, mock_send_sms, user, other_user
    ):
        group = Group.objects.create(
            name="Inbound Test Group",
            created_by=user,
            proxy_number="+15559990000",
        )
        Membership.objects.create(user=user, group=group, is_admin=True)
        Membership.objects.create(user=other_user, group=group)
        mock_send_sms.return_value = "SM456"

        sent_count = fan_out_inbound_group_message(
            from_phone_number=user.phone_number,
            to_proxy_number=group.proxy_number,
            body="Hello team",
        )

        assert sent_count == 1
        mock_send_sms.assert_called_once_with(
            to_phone_number=other_user.phone_number,
            body=build_group_message_body(sender=user, body="Hello team"),
            from_phone_number=group.proxy_number,
        )

    @patch("group_text.sms.send_sms")
    def test_fan_out_inbound_group_message_returns_zero_for_non_member_sender(
        self, mock_send_sms, user, other_user
    ):
        group = Group.objects.create(
            name="Inbound Unknown Sender Group",
            created_by=user,
            proxy_number="+15559990001",
        )
        Membership.objects.create(user=user, group=group, is_admin=True)

        sent_count = fan_out_inbound_group_message(
            from_phone_number=other_user.phone_number,
            to_proxy_number=group.proxy_number,
            body="Hello",
        )

        assert sent_count == 0
        mock_send_sms.assert_not_called()
