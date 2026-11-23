"""Fixtures shared by the b2b tests."""

from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image


@pytest.fixture
def logo_upload(settings, tmp_path):
    """Return a factory for PNG uploads, stored under a temporary MEDIA_ROOT."""

    settings.MEDIA_ROOT = str(tmp_path)

    def _upload(name="logo.png"):
        buffer = BytesIO()
        Image.new("RGBA", (200, 100), (163, 31, 52, 255)).save(buffer, "PNG")
        return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")

    return _upload
