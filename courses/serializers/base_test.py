"""Tests for courses.serializers.base"""

import pytest

from cms.factories import CoursePageFactory
from courses.serializers.base import get_thumbnail_url

pytestmark = pytest.mark.django_db

S3_STORAGES = {
    "default": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@pytest.mark.parametrize(
    ("custom_domain", "expected_prefix"),
    [
        (None, "https://test-bucket.s3.amazonaws.com/"),
        ("mitxonline.example.com/media", "https://mitxonline.example.com/media/"),
    ],
)
def test_get_thumbnail_url_s3(settings, custom_domain, expected_prefix):
    """With S3 storage, thumbnail URLs use AWS_S3_CUSTOM_DOMAIN when it's set"""
    page = CoursePageFactory.create()
    settings.AWS_STORAGE_BUCKET_NAME = "test-bucket"
    settings.AWS_S3_CUSTOM_DOMAIN = custom_domain
    settings.STORAGES = S3_STORAGES

    assert get_thumbnail_url(page) == expected_prefix + page.feature_image.file.name
