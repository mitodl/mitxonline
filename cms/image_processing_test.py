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
from cms.management.commands.bulk_populate_signatories import Command

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


def _encode(image, fmt, **save_kwargs):
    buffer = BytesIO()
    image.save(buffer, fmt, **save_kwargs)
    return buffer.getvalue()


def _upload(name, data):
    upload = SimpleUploadedFile(name, data)
    WagtailImageField().clean(upload)
    upload.seek(0)
    return get_image_model().objects.create(title=name, file=upload)


def _animated_gif():
    frames = [PILImage.new("P", (800, 400), color) for color in (1, 2)]
    return _encode(frames[0], "GIF", save_all=True, append_images=frames[1:])


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("cmyk.jpg", _encode(PILImage.new("CMYK", (800, 400)), "JPEG")),
        ("gray.jpg", _encode(PILImage.new("L", (800, 400)), "JPEG")),
        (
            "palette.png",
            _encode(PILImage.new("P", (800, 400)), "PNG", transparency=0),
        ),
        ("gray-alpha.png", _encode(PILImage.new("LA", (800, 400)), "PNG")),
        ("16bit.png", _encode(PILImage.new("I;16", (800, 400)), "PNG")),
        ("animated.gif", _animated_gif()),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_wagtail_renditions_color_modes(name, data):
    """Non-RGB uploads (scans, logos, exports) should render the certificate's signature size"""
    image = _upload(name, data)
    rendition = image.get_rendition("max-150x50")
    assert (rendition.width, rendition.height) == (100, 50)


@pytest.mark.django_db
def test_wagtail_rendition_applies_exif_orientation():
    """A phone photo with an EXIF rotation should be resized in its displayed orientation"""
    exif = PILImage.Exif()
    exif[0x0112] = 6  # Orientation: rotate 90 degrees clockwise
    data = _encode(PILImage.new("RGB", (800, 400)), "JPEG", exif=exif)
    image = _upload("rotated.jpg", data)
    rendition = image.get_rendition("max-150x50")
    assert (rendition.width, rendition.height) == (25, 50)


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("mismatch.jpg", _image_bytes("PNG")),
        ("text.png", b"not an image"),
        ("vector.svg", b'<svg xmlns="http://www.w3.org/2000/svg"/>'),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_wagtail_upload_rejects_invalid_files(name, data):
    """Uploads whose content isn't a valid image of the allowed type should be rejected"""
    with pytest.raises(ValidationError):
        WagtailImageField().clean(SimpleUploadedFile(name, data))


def test_wagtail_upload_rejects_too_many_pixels(settings):
    """The pixel limit should reject oversized images before they're processed"""
    settings.WAGTAILIMAGES_MAX_IMAGE_PIXELS = 800 * 400 - 1
    with pytest.raises(ValidationError):
        WagtailImageField().clean(SimpleUploadedFile("big.png", _image_bytes("PNG")))


@pytest.mark.django_db
def test_bulk_populate_signatories_saves_downloaded_image(mocker):
    """A downloaded signature should be saved as a Wagtail image with its real size"""
    mocker.patch(
        "cms.management.commands.bulk_populate_signatories.requests.get"
    ).return_value.content = _image_bytes("PNG")

    image = Command().fetch_or_create_signature_image(
        "Jane Doe", "https://example.com/sig.png"
    )

    assert (image.width, image.height) == (800, 400)
    rendition = image.get_rendition("max-150x50")
    assert (rendition.width, rendition.height) == (100, 50)
