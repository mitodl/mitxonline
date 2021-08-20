"""Utils tests"""
from mitol.common.utils.urls import remove_password_from_url
from mitol.common.utils.webpack import webpack_public_path

from main.models import AuditModel
from main.utils import get_field_names, get_js_settings


def test_get_field_names():
    """
    Assert that get_field_names does not include related fields
    """
    assert set(get_field_names(AuditModel)) == {
        "data_before",
        "data_after",
        "acting_user",
        "created_on",
        "updated_on",
    }


def test_get_js_settings(settings, rf):
    """Test get_js_settings"""
    settings.GA_TRACKING_ID = "fake"
    settings.ENVIRONMENT = "test"
    settings.VERSION = "4.5.6"
    settings.EMAIL_SUPPORT = "support@text.com"
    settings.USE_WEBPACK_DEV_SERVER = False
    settings.RECAPTCHA_SITE_KEY = "fake_key"

    request = rf.get("/")

    assert get_js_settings(request) == {
        "gaTrackingID": "fake",
        "public_path": webpack_public_path(request),
        "environment": settings.ENVIRONMENT,
        "sentry_dsn": remove_password_from_url(settings.SENTRY_DSN),
        "release_version": settings.VERSION,
        "recaptchaKey": settings.RECAPTCHA_SITE_KEY,
        "support_email": settings.EMAIL_SUPPORT,
        "site_name": settings.SITE_NAME,
    }
