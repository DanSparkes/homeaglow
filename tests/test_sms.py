from unittest.mock import Mock, patch

import pytest
from django.test import override_settings

from group_text.sms import build_welcome_sms_body, send_sms, send_welcome_sms


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
