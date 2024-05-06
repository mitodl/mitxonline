"""retire user test"""

import hashlib

import pytest
from django.contrib.auth import get_user_model
from social_django.models import UserSocialAuth

from users.factories import UserFactory, UserSocialAuthFactory
from users.management.commands import retire_users
from users.models import BlockList

User = get_user_model()

COMMAND = retire_users.Command()


@pytest.mark.django_db
def test_single_success(mocker):
    """Test retire_users command success with one user"""
    test_username = "test_user"

    mock_bulk_retire_edx_users = mocker.patch(
        "users.management.commands.retire_users.bulk_retire_edx_users",
        return_value={"successful_user_retirements": [test_username]},
    )

    user = UserFactory.create(username=test_username, is_active=True)
    UserSocialAuthFactory.create(user=user, provider="edX")

    assert user.is_active is True
    assert "retired_email" not in user.email
    assert UserSocialAuth.objects.filter(user=user).count() == 1

    COMMAND.handle("retire_users", users=[test_username])

    user.refresh_from_db()
    assert user.is_active is False
    assert "retired_email" in user.email
    assert UserSocialAuth.objects.filter(user=user).count() == 0
    mock_bulk_retire_edx_users.assert_called()


@pytest.mark.django_db
def test_multiple_success(mocker):
    """Test retire_users command success with more than one user"""
    test_usernames = ["foo", "bar", "baz"]

    mock_bulk_retire_edx_users = mocker.patch(
        "users.management.commands.retire_users.bulk_retire_edx_users",
        return_value={"successful_user_retirements": test_usernames},
    )

    for username in test_usernames:
        user = UserFactory.create(username=username, is_active=True)
        UserSocialAuthFactory.create(user=user, provider="not_edx")

        assert user.is_active is True
        assert "retired_email" not in user.email
        assert UserSocialAuth.objects.filter(user=user).count() == 1

    COMMAND.handle("retire_users", users=test_usernames)

    for user_name in test_usernames:
        user = User.objects.get(username=user_name)
        assert user.is_active is False
        assert "retired_email" in user.email
        assert UserSocialAuth.objects.filter(user=user).count() == 0
    mock_bulk_retire_edx_users.assert_called()


@pytest.mark.django_db
def test_retire_user_with_email(mocker):
    """Test retire_users command success with user email"""
    test_email = "test@email.com"

    user = UserFactory.create(email=test_email, is_active=True)
    UserSocialAuthFactory.create(user=user, provider="edX")

    mock_bulk_retire_edx_users = mocker.patch(
        "users.management.commands.retire_users.bulk_retire_edx_users",
        return_value={"successful_user_retirements": [user.username]},
    )

    assert user.is_active is True
    assert "retired_email" not in user.email
    assert UserSocialAuth.objects.filter(user=user).count() == 1

    COMMAND.handle("retire_users", users=[test_email])

    user.refresh_from_db()
    assert user.is_active is False
    assert "retired_email" in user.email
    assert UserSocialAuth.objects.filter(user=user).count() == 0
    mock_bulk_retire_edx_users.assert_called_with(user.username)


@pytest.mark.django_db
def test_retire_user_blocking_with_email(mocker):
    """Test retire_users command success with user email"""
    test_email = "test@email.com"

    user = UserFactory.create(email=test_email, is_active=True)
    UserSocialAuthFactory.create(user=user, provider="edX")
    email = user.email
    hashed_email = hashlib.md5(email.lower().encode("utf-8")).hexdigest()  # noqa: S324
    assert user.is_active is True
    assert "retired_email" not in user.email
    assert UserSocialAuth.objects.filter(user=user).count() == 1
    assert BlockList.objects.all().count() == 0

    mock_bulk_retire_edx_users = mocker.patch(
        "users.management.commands.retire_users.bulk_retire_edx_users",
        return_value={"successful_user_retirements": [user.username]},
    )
    COMMAND.handle("retire_users", users=[test_email], block_users=True)

    user.refresh_from_db()
    assert user.is_active is False
    assert "retired_email" in user.email
    assert UserSocialAuth.objects.filter(user=user).count() == 0
    assert BlockList.objects.all().count() == 1
    assert BlockList.objects.filter(hashed_email=hashed_email).count() == 1
    mock_bulk_retire_edx_users.assert_called_with(user.username)


@pytest.mark.django_db
def test_multiple_success_blocking_user(mocker):
    """Test retire_users command blocking emails success with more than one user"""
    test_usernames = ["foo", "bar", "baz"]
    mock_bulk_retire_edx_users = mocker.patch(
        "users.management.commands.retire_users.bulk_retire_edx_users",
        return_value={"successful_user_retirements": test_usernames},
    )

    for username in test_usernames:
        user = UserFactory.create(username=username, is_active=True)
        UserSocialAuthFactory.create(user=user, provider="not_edx")

        assert user.is_active is True
        assert "retired_email" not in user.email
        assert UserSocialAuth.objects.filter(user=user).count() == 1
        assert BlockList.objects.all().count() == 0

    COMMAND.handle("retire_users", users=test_usernames, block_users=True)

    for user_name in test_usernames:
        user = User.objects.get(username=user_name)
        assert user.is_active is False
        assert "retired_email" in user.email
        assert UserSocialAuth.objects.filter(user=user).count() == 0

    assert BlockList.objects.all().count() == 3
    mock_bulk_retire_edx_users.assert_called()


@pytest.mark.django_db
def test_user_blocking_if_not_requested(mocker):
    """Test retire_users command success but it should not block user(s) if not requested"""
    test_email = "test@email.com"

    user = UserFactory.create(email=test_email, is_active=True)
    UserSocialAuthFactory.create(user=user, provider="edX")
    email = user.email
    hashed_email = hashlib.md5(email.lower().encode("utf-8")).hexdigest()  # noqa: S324, F841
    assert user.is_active is True
    assert "retired_email" not in user.email
    assert UserSocialAuth.objects.filter(user=user).count() == 1
    assert BlockList.objects.all().count() == 0

    mock_bulk_retire_edx_users = mocker.patch(
        "users.management.commands.retire_users.bulk_retire_edx_users",
        return_value={"successful_user_retirements": [user.username]},
    )
    COMMAND.handle("retire_users", users=[test_email])

    user.refresh_from_db()
    assert user.is_active is False
    assert "retired_email" in user.email
    assert UserSocialAuth.objects.filter(user=user).count() == 0
    assert BlockList.objects.all().count() == 0
    mock_bulk_retire_edx_users.assert_called_with(user.username)
