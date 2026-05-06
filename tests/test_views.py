from unittest.mock import patch

import pytest
from django.urls import reverse

from group_text.models import Group, Membership, User


@pytest.mark.django_db
class TestLoginView:
    def test_login_view_get_renders_form(self, client):
        # Happy path: the sign-in page should render for anonymous users.
        response = client.get(reverse("login"))

        assert response.status_code == 200
        assert "Sign in" in response.content.decode()

    def test_login_view_authenticated_user_redirects_home(self, client, user):
        # Edge case: authenticated users should not see the login form again.
        client.force_login(user)

        response = client.get(reverse("login"))

        assert response.status_code == 302
        assert response.url == reverse("home")

    def test_login_view_post_valid_credentials_redirects_home(self, client, user):
        # Happy path: valid credentials log the user in and create an auth session.
        response = client.post(
            reverse("login"),
            {"phone_number": user.phone_number, "password": "password123"},
        )

        assert response.status_code == 302
        assert response.url == reverse("home")
        assert "_auth_user_id" in client.session

    def test_login_view_post_honors_next_query_parameter(self, client, user):
        # Happy path: the next querystring controls the redirect target after login.
        response = client.post(
            f"{reverse('login')}?next={reverse('group-list')}",
            {"phone_number": user.phone_number, "password": "password123"},
        )

        assert response.status_code == 302
        assert response.url == reverse("group-list")

    def test_login_view_post_invalid_credentials_shows_error(self, client, user):
        # Edge case: invalid credentials should re-render the page with an error.
        response = client.post(
            reverse("login"),
            {"phone_number": user.phone_number, "password": "wrong-password"},
        )

        assert response.status_code == 200
        assert "Invalid phone number or password." in response.content.decode()

    def test_login_view_put_behaves_like_get(self, client):
        # Edge case: this view is not method-restricted, so non-POST falls through to render.
        response = client.put(reverse("login"))

        assert response.status_code == 200
        assert "Sign in" in response.content.decode()


@pytest.mark.django_db
class TestRegisterView:
    def test_register_view_get_renders_form(self, client):
        # Happy path: anonymous users can load the registration page.
        response = client.get(reverse("register"))

        assert response.status_code == 200
        assert "Create an account" in response.content.decode()

    def test_register_view_authenticated_user_redirects_home(self, client, user):
        # Edge case: authenticated users should be redirected away from registration.
        client.force_login(user)

        response = client.get(reverse("register"))

        assert response.status_code == 302
        assert response.url == reverse("home")

    def test_register_view_post_creates_user_and_logs_them_in(self, client):
        # Happy path: a valid registration creates the user and starts a session.
        response = client.post(
            reverse("register"),
            {
                "phone_number": "+15550000009",
                "name": "New User",
                "password": "password123",
            },
        )

        assert response.status_code == 302
        assert response.url == reverse("home")
        assert User.objects.filter(
            phone_number="+15550000009", name="New User"
        ).exists()
        assert "_auth_user_id" in client.session

    def test_register_view_post_missing_fields_shows_error_and_preserves_input(
        self, client
    ):
        # Edge case: blank required fields should re-render with validation feedback.
        response = client.post(
            reverse("register"),
            {"phone_number": "", "name": "", "password": ""},
        )

        content = response.content.decode()

        assert response.status_code == 200
        assert "All fields are required." in content
        assert 'value=""' in content

    def test_register_view_post_short_password_shows_error(self, client):
        # Edge case: short passwords should be rejected before user creation.
        response = client.post(
            reverse("register"),
            {
                "phone_number": "+15550000010",
                "name": "Short Password",
                "password": "short",
            },
        )

        assert response.status_code == 200
        assert "Password must be at least 8 characters." in response.content.decode()
        assert not User.objects.filter(phone_number="+15550000010").exists()

    def test_register_view_post_duplicate_phone_number_shows_error(self, client, user):
        # Edge case: existing phone numbers should remain unique.
        response = client.post(
            reverse("register"),
            {
                "phone_number": user.phone_number,
                "name": "Duplicate",
                "password": "password123",
            },
        )

        assert response.status_code == 200
        assert "That phone number is already registered." in response.content.decode()

    def test_register_view_put_behaves_like_get(self, client):
        # Edge case: this view is also not method-restricted, so non-POST renders the page.
        response = client.put(reverse("register"))

        assert response.status_code == 200
        assert "Create an account" in response.content.decode()


@pytest.mark.django_db
class TestLogoutView:
    def test_logout_view_post_logs_user_out(self, client, user):
        # Happy path: logout clears the auth session and redirects to login.
        client.force_login(user)

        response = client.post(reverse("logout"))

        assert response.status_code == 302
        assert response.url == reverse("login")
        assert "_auth_user_id" not in client.session

    def test_logout_view_get_not_allowed(self, client):
        # Edge case: the view is POST-only.
        response = client.get(reverse("logout"))

        assert response.status_code == 405

    def test_logout_view_requires_csrf_token_when_enforced(self, csrf_client, user):
        # Edge case: CSRF protection still applies when using a client with checks enabled.
        csrf_client.force_login(user)

        response = csrf_client.post(reverse("logout"))

        assert response.status_code == 403


@pytest.mark.django_db
class TestHomeView:
    def test_home_view_authenticated_user_renders_page(
        self, authenticated_client, user
    ):
        # Happy path: logged-in users can load the groups homepage.
        response = authenticated_client.get(reverse("home"))

        content = response.content.decode()

        assert response.status_code == 200
        assert "Groups" in content
        assert user.name in content

    def test_home_view_redirects_unauthenticated_user(self, client):
        # Edge case: login is required for the homepage.
        response = client.get(reverse("home"))

        assert response.status_code == 302
        assert response.url == f"{reverse('login')}?next={reverse('home')}"


@pytest.mark.django_db
class TestGroupListView:
    def test_group_list_view_renders_empty_state(self, authenticated_client):
        # Happy path for an empty queryset: the partial should render the empty-state copy.
        response = authenticated_client.get(reverse("group-list"))

        assert response.status_code == 200
        assert "No groups yet." in response.content.decode()

    def test_group_list_view_shows_groups_membership_and_counts(
        self, authenticated_client, user, other_user, member_group, second_group
    ):
        # Happy path: the list should include membership state and aggregate counts.
        Membership.objects.create(user=other_user, group=second_group, is_admin=True)

        response = authenticated_client.get(reverse("group-list"))

        content = response.content.decode()

        assert response.status_code == 200
        assert member_group.name in content
        assert second_group.name in content
        assert "2 members" in content
        assert "Member" in content
        assert "Join" in content

    def test_group_list_view_filters_by_query(
        self, authenticated_client, group, second_group
    ):
        # Edge case: query filtering should include matching names and exclude others.
        response = authenticated_client.get(reverse("group-list"), {"q": "family"})

        content = response.content.decode()

        assert response.status_code == 200
        assert group.name in content
        assert second_group.name not in content
        assert (
            'matching "<span class="text-gray-600 font-medium">family</span>"'
            in content
        )

    def test_group_list_view_shows_no_match_state(self, authenticated_client, group):
        # Edge case: a search with no results should render the no-match state.
        response = authenticated_client.get(reverse("group-list"), {"q": "missing"})

        assert response.status_code == 200
        assert (
            'No groups matching "<strong>missing</strong>".'
            in response.content.decode()
        )

    def test_group_list_view_redirects_unauthenticated_user(self, client):
        # Edge case: anonymous users should be redirected to login.
        response = client.get(reverse("group-list"))

        assert response.status_code == 302
        assert response.url == f"{reverse('login')}?next={reverse('group-list')}"

    def test_group_list_view_post_not_allowed(self, authenticated_client):
        # Edge case: the endpoint is GET-only.
        response = authenticated_client.post(reverse("group-list"))

        assert response.status_code == 405


@pytest.mark.django_db
class TestGroupCreateView:
    def test_group_create_view_creates_group_and_admin_membership(
        self, authenticated_client, user
    ):
        # Happy path: a valid POST creates the group and an admin membership for the creator.
        response = authenticated_client.post(
            reverse("group-create"), {"name": "Book Club"}
        )

        group = Group.objects.get(name="Book Club")

        assert response.status_code == 200
        assert response.content == b""
        assert response["HX-Trigger"] == "group-created"
        assert Membership.objects.filter(user=user, group=group, is_admin=True).exists()

    def test_group_create_view_rejects_blank_name(self, authenticated_client):
        # Edge case: missing form data should return inline validation HTML.
        response = authenticated_client.post(reverse("group-create"), {"name": "   "})

        assert response.status_code == 200
        assert "Group name is required." in response.content.decode()

    def test_group_create_view_rejects_overlong_name(self, authenticated_client):
        # Edge case: names longer than 100 chars should be rejected.
        response = authenticated_client.post(
            reverse("group-create"), {"name": "a" * 101}
        )

        assert response.status_code == 200
        assert "Name must be 100 characters or fewer." in response.content.decode()

    def test_group_create_view_rejects_case_insensitive_duplicates(
        self, authenticated_client, group
    ):
        # Edge case: duplicate names should be detected case-insensitively.
        response = authenticated_client.post(
            reverse("group-create"), {"name": group.name.upper()}
        )

        assert response.status_code == 200
        assert (
            f"<strong>{group.name.upper()}</strong> already exists."
            in response.content.decode()
        )

    def test_group_create_view_redirects_unauthenticated_user(self, client):
        # Edge case: anonymous users cannot create groups.
        response = client.post(reverse("group-create"), {"name": "Blocked"})

        assert response.status_code == 302
        assert response.url == f"{reverse('login')}?next={reverse('group-create')}"

    def test_group_create_view_get_not_allowed(self, authenticated_client):
        # Edge case: the endpoint is POST-only.
        response = authenticated_client.get(reverse("group-create"))

        assert response.status_code == 405

    def test_group_create_view_requires_csrf_token_when_enforced(
        self, csrf_client, user
    ):
        # Edge case: CSRF middleware should reject state-changing requests without a token.
        csrf_client.force_login(user)

        response = csrf_client.post(
            reverse("group-create"), {"name": "Blocked by CSRF"}
        )

        assert response.status_code == 403


@pytest.mark.django_db
class TestGroupJoinView:
    @patch("group_text.views.send_welcome_sms")
    def test_group_join_view_creates_membership_and_returns_partial(
        self, mock_send_welcome_sms, authenticated_client, group, user
    ):
        # Happy path: joining creates a membership and returns the updated card section.
        response = authenticated_client.post(reverse("group-join", args=[group.id]))

        content = response.content.decode()

        assert response.status_code == 200
        assert response["HX-Trigger"] == "membership-changed"
        assert Membership.objects.filter(user=user, group=group).exists()
        assert "Member" in content
        assert "Leave" in content
        assert "1 member" in content
        mock_send_welcome_sms.assert_called_once_with(user=user, group=group)

    @patch("group_text.views.send_welcome_sms")
    def test_group_join_view_is_idempotent_for_existing_member(
        self, mock_send_welcome_sms, authenticated_client, member_group, user
    ):
        # Edge case: repeated joins should not create duplicate through rows.
        response = authenticated_client.post(
            reverse("group-join", args=[member_group.id])
        )

        assert response.status_code == 200
        assert Membership.objects.filter(user=user, group=member_group).count() == 1
        mock_send_welcome_sms.assert_not_called()

    def test_group_join_view_returns_404_for_missing_group(self, authenticated_client):
        # Edge case: invalid identifiers should produce a 404.
        response = authenticated_client.post(reverse("group-join", args=[99999]))

        assert response.status_code == 404

    def test_group_join_view_redirects_unauthenticated_user(self, client, group):
        # Edge case: anonymous users cannot join groups.
        response = client.post(reverse("group-join", args=[group.id]))

        assert response.status_code == 302
        assert (
            response.url
            == f"{reverse('login')}?next={reverse('group-join', args=[group.id])}"
        )

    def test_group_join_view_get_not_allowed(self, authenticated_client, group):
        # Edge case: the endpoint is POST-only.
        response = authenticated_client.get(reverse("group-join", args=[group.id]))

        assert response.status_code == 405


@pytest.mark.django_db
class TestGroupLeaveView:
    def test_group_leave_view_removes_membership_and_returns_partial(
        self, authenticated_client, member_group, user
    ):
        # Happy path: leaving removes the membership and returns a join button.
        response = authenticated_client.post(
            reverse("group-leave", args=[member_group.id])
        )

        content = response.content.decode()

        assert response.status_code == 200
        assert response["HX-Trigger"] == "membership-changed"
        assert not Membership.objects.filter(user=user, group=member_group).exists()
        assert "Join" in content
        assert "Member" not in content
        assert "1 member" in content

    def test_group_leave_view_is_safe_for_non_member(self, authenticated_client, group):
        # Edge case: leaving a group without a membership should still succeed cleanly.
        response = authenticated_client.post(reverse("group-leave", args=[group.id]))

        assert response.status_code == 200
        assert "0 members" in response.content.decode()

    def test_group_leave_view_returns_404_for_missing_group(self, authenticated_client):
        # Edge case: invalid identifiers should produce a 404.
        response = authenticated_client.post(reverse("group-leave", args=[99999]))

        assert response.status_code == 404

    def test_group_leave_view_redirects_unauthenticated_user(self, client, group):
        # Edge case: anonymous users cannot leave groups.
        response = client.post(reverse("group-leave", args=[group.id]))

        assert response.status_code == 302
        assert (
            response.url
            == f"{reverse('login')}?next={reverse('group-leave', args=[group.id])}"
        )

    def test_group_leave_view_get_not_allowed(self, authenticated_client, group):
        # Edge case: the endpoint is POST-only.
        response = authenticated_client.get(reverse("group-leave", args=[group.id]))

        assert response.status_code == 405


@pytest.mark.django_db
class TestTwilioSMSWebhookView:
    @patch("group_text.views.fan_out_inbound_group_message")
    @patch("group_text.views.verify_twilio_signature")
    def test_webhook_view_verifies_signature_and_fans_out(
        self, mock_verify_signature, mock_fan_out, client
    ):
        mock_verify_signature.return_value = True

        response = client.post(
            reverse("twilio-sms-webhook"),
            {
                "From": "+15550000001",
                "To": "+15559990000",
                "Body": "Hello group",
            },
            HTTP_X_TWILIO_SIGNATURE="valid-signature",
        )

        assert response.status_code == 200
        assert response["Content-Type"] == "text/xml"
        assert response.content.decode() == "<Response></Response>"
        mock_verify_signature.assert_called_once()
        mock_fan_out.assert_called_once_with(
            from_phone_number="+15550000001",
            to_proxy_number="+15559990000",
            body="Hello group",
        )

    @patch("group_text.views.fan_out_inbound_group_message")
    @patch("group_text.views.verify_twilio_signature")
    def test_webhook_view_rejects_invalid_signature(
        self, mock_verify_signature, mock_fan_out, client
    ):
        mock_verify_signature.return_value = False

        response = client.post(
            reverse("twilio-sms-webhook"),
            {"From": "+15550000001", "To": "+15559990000", "Body": "Hello"},
            HTTP_X_TWILIO_SIGNATURE="bad-signature",
        )

        assert response.status_code == 403
        assert "Invalid Twilio signature." in response.content.decode()
        mock_fan_out.assert_not_called()

    @patch("group_text.views.fan_out_inbound_group_message")
    @patch("group_text.views.verify_twilio_signature")
    def test_webhook_view_is_csrf_exempt(
        self, mock_verify_signature, mock_fan_out, csrf_client
    ):
        mock_verify_signature.return_value = True

        response = csrf_client.post(
            reverse("twilio-sms-webhook"),
            {"From": "+15550000001", "To": "+15559990000", "Body": "Hello"},
            HTTP_X_TWILIO_SIGNATURE="valid-signature",
        )

        assert response.status_code == 200
        mock_fan_out.assert_called_once()

    def test_webhook_view_get_not_allowed(self, client):
        response = client.get(reverse("twilio-sms-webhook"))

        assert response.status_code == 405
