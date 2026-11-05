"""Tests that run real image processing (Pillow, via Wagtail/willow and Django).

These exist so a Pillow, willow or Wagtail upgrade is exercised by CI on the
paths the app actually uses, rather than needing manual checks on RC.
"""

from io import BytesIO

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import Context, Template
from PIL import Image as PILImage
from wagtail.images import get_image_model
from wagtail.images.fields import WagtailImageField
from wagtail.images.tests.utils import get_test_image_file

from b2b.models import OrganizationPage

# Wagtail's Image.generate_rendition_file passes filter.run() a
# SpooledTemporaryFile and never closes it.
pytestmark = pytest.mark.filterwarnings(
    "ignore:Exception ignored in. <function SpooledTemporaryFile.__del__"
    ":pytest.PytestUnraisableExceptionWarning",
    "ignore:Unclosed file <tempfile.SpooledTemporaryFile:ResourceWarning",
)


def _image_bytes(fmt):
    buffer = BytesIO()
    mode = "RGB" if fmt == "JPEG" else "RGBA"
    PILImage.new(mode, (800, 400), (163, 31, 52, 255)).save(buffer, fmt)
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    """Write uploaded files and renditions to a temporary directory."""
    settings.MEDIA_ROOT = str(tmp_path)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("fmt", "extension"),
    [
        ("JPEG", "jpg"),
        ("JPEG", "jpeg"),
        ("PNG", "png"),
        ("GIF", "gif"),
        ("WEBP", "webp"),
        ("AVIF", "avif"),
    ],
)
def test_wagtail_image_renditions(fmt, extension):
    """Uploaded images in each allowed format should produce resized renditions"""
    upload = SimpleUploadedFile(f"test.{extension}", _image_bytes(fmt))
    # The validation an admin upload goes through: format detection and size checks.
    WagtailImageField().clean(upload)
    upload.seek(0)
    image = get_image_model().objects.create(title=fmt, file=upload)
    assert (image.width, image.height) == (800, 400)

    rendition = image.get_rendition("max-150x50")
    assert (rendition.width, rendition.height) == (100, 50)

    rendition = image.get_rendition("fill-100x100|format-webp")
    assert (rendition.width, rendition.height) == (100, 100)
    assert rendition.file.name.endswith(".webp")


@pytest.mark.django_db
def test_signature_image_tag():
    """The certificate page's signature {% image %} tag should render a resized image"""
    image = get_image_model().objects.create(
        title="Signature", file=get_test_image_file(size=(600, 100))
    )
    html = Template(
        '{% load wagtailimages_tags %}{% image img max-150x50 alt="" %}'
    ).render(Context({"img": image}))
    assert 'width="150"' in html
    assert 'height="25"' in html


def test_organization_logo_validation():
    """The organization logo field should accept a real image and reject anything else"""
    field = OrganizationPage._meta.get_field("logo").formfield()  # noqa: SLF001

    assert field.clean(SimpleUploadedFile("logo.png", _image_bytes("PNG")))

    with pytest.raises(ValidationError):
        field.clean(SimpleUploadedFile("logo.png", b"not an image"))
