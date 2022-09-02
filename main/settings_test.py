"""
Validate that our settings functions work
"""

import importlib
import sys
from unittest import mock
from types import SimpleNamespace

import pytest
import semantic_version
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from mitol.common import envs, pytest_utils


# this is a test, but pylint thinks it ends up being unused
# hence we import the entire module and assign it here
test_app_json_modified = pytest_utils.test_app_json_modified


@pytest.fixture(autouse=True)
def settings_sandbox(monkeypatch):
    """Cleanup settings after a test"""

    monkeypatch.delenv("MITX_ONLINE_DB_DISABLE_SSL", raising=False)
    monkeypatch.delenv("CSRF_TRUSTED_ORIGINS", raising=False)
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "main.settings")
    monkeypatch.setenv("MAILGUN_SENDER_DOMAIN", "mailgun.fake.domain")
    monkeypatch.setenv("MAILGUN_KEY", "fake_mailgun_key")
    monkeypatch.setenv("MITX_ONLINE_BASE_URL", "http://localhost:8013")

    def _get():
        return vars(sys.modules["main.settings"])

    def _patch(overrides):

        for key, value in overrides.items():
            monkeypatch.setenv(key, value)

        return _reload()

    def _reload():
        """
        Reload settings module with cleanup to restore it.

        Returns:
            dict: dictionary of the newly reloaded settings ``vars``
        """
        envs.env.reload()
        return _get()

    yield SimpleNamespace(
        patch=_patch,
        reload=_reload,
        get=_get,
    )

    _reload()


def test_s3_settings(settings_sandbox):
    """Verify that we enable and configure S3 with a variable"""
    # Unset, we don't do S3
    settings_vars = settings_sandbox.patch({"MITX_ONLINE_USE_S3": "False"})

    assert settings_vars.get("DEFAULT_FILE_STORAGE") is None

    with pytest.raises(ImproperlyConfigured):
        settings_sandbox.patch({"MITX_ONLINE_USE_S3": "True"})

    # Verify it all works with it enabled and configured 'properly'
    settings_vars = settings_sandbox.patch(
        {
            "MITX_ONLINE_USE_S3": "True",
            "AWS_ACCESS_KEY_ID": "1",
            "AWS_SECRET_ACCESS_KEY": "2",
            "AWS_STORAGE_BUCKET_NAME": "3",
        }
    )
    assert (
        settings_vars.get("DEFAULT_FILE_STORAGE")
        == "storages.backends.s3boto3.S3Boto3Storage"
    )


def test_admin_settings(settings_sandbox, settings):
    """Verify that we configure email with environment variable"""

    settings_vars = settings_sandbox.patch({"MITX_ONLINE_ADMIN_EMAIL": ""})
    assert settings_vars["ADMINS"] == ()

    test_admin_email = "cuddle_bunnies@example.com"
    settings_vars = settings_sandbox.patch(
        {"MITX_ONLINE_ADMIN_EMAIL": test_admin_email}
    )
    assert (("Admins", test_admin_email),) == settings_vars["ADMINS"]

    # Manually set ADMIN to our test setting and verify e-mail
    # goes where we expect
    settings.ADMINS = (("Admins", test_admin_email),)
    mail.mail_admins("Test", "message")
    assert test_admin_email in mail.outbox[0].to


def test_csrf_trusted_origins(settings_sandbox):
    """Verify that we can configure CSRF_TRUSTED_ORIGINS with a var"""
    # Test the default
    settings_vars = settings_sandbox.get()
    assert settings_vars.get("CSRF_TRUSTED_ORIGINS") == []

    # Verify the env var works
    settings_vars = settings_sandbox.patch(
        {
            "CSRF_TRUSTED_ORIGINS": "some.domain.com, some.other.domain.org",
        }
    )
    assert settings_vars.get("CSRF_TRUSTED_ORIGINS") == [
        "some.domain.com",
        "some.other.domain.org",
    ]


def test_db_ssl_enable(monkeypatch, settings_sandbox):
    """Verify that we can enable/disable database SSL with a var"""
    # Check default state is SSL on
    settings_vars = settings_sandbox.reload()
    assert settings_vars["DATABASES"]["default"]["OPTIONS"] == {"sslmode": "require"}

    # Check enabling the setting explicitly
    settings_vars = settings_sandbox.patch({"MITX_ONLINE_DB_DISABLE_SSL": "True"})
    assert settings_vars["DATABASES"]["default"]["OPTIONS"] == {}

    # Disable it
    settings_vars = settings_sandbox.patch({"MITX_ONLINE_DB_DISABLE_SSL": "False"})
    assert settings_vars["DATABASES"]["default"]["OPTIONS"] == {"sslmode": "require"}


def test_semantic_version(settings):
    """
    Verify that we have a semantic compatible version.
    """
    semantic_version.Version(settings.VERSION)


def test_server_side_cursors_disabled(settings_sandbox):
    """DISABLE_SERVER_SIDE_CURSORS should be true by default"""
    settings_vars = settinGINgs_sandbox.get()
    assert (
        settings_vars["DEFAULT_DATABASE_CONFIG"]["DISABLE_SERVER_SIDE_CURSORS"] is True
    )


def test_server_side_cursors_enabled(settings_sandbox):
    """DISABLE_SERVER_SIDE_CURSORS should be false if MITX_ONLINE_DB_DISABLE_SS_CURSORS is false"""
    settings_vars = settings_sandbox.patch(
        {"MITX_ONLINE_DB_DISABLE_SS_CURSORS": "False"}
    )
    assert (
        settings_vars["DEFAULT_DATABASE_CONFIG"]["DISABLE_SERVER_SIDE_CURSORS"] is False
    )
