import pytest

from group_text.models import Group, Membership, User


@pytest.fixture
def user(db):
    return User.objects.create_user(
        phone_number="+15550000001",
        name="Primary User",
        password="password123",
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        phone_number="+15550000002",
        name="Admin User",
        password="password123",
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        phone_number="+15550000003",
        name="Other User",
        password="password123",
    )


@pytest.fixture
def authenticated_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def csrf_client():
    from django.test import Client

    return Client(enforce_csrf_checks=True)


@pytest.fixture
def group(db, user):
    return Group.objects.create(name="Family Chat", created_by=user)


@pytest.fixture
def second_group(db, other_user):
    return Group.objects.create(name="Running Club", created_by=other_user)


@pytest.fixture
def member_group(db, user, other_user):
    group = Group.objects.create(name="Project Team", created_by=other_user)
    Membership.objects.create(user=user, group=group)
    Membership.objects.create(user=other_user, group=group, is_admin=True)
    return group
