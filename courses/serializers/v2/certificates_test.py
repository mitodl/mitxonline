"""Tests for the certificates serializers."""

import pytest
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from cms.factories import CoursePageFactory, ProgramPageFactory
from courses.factories import CourseRunCertificateFactory, ProgramCertificateFactory
from courses.serializers.v2.certificates import (
    CourseRunCertificateSerializer,
    ProgramCertificateSerializer,
)
from courses.serializers.v2.courses import CourseRunWithCourseSerializer
from courses.serializers.v2.programs import ProgramSerializer
from main.test_utils import assert_drf_json_equal
from users.serializers import PublicUserSerializer

pytestmark = [pytest.mark.django_db]


@pytest.fixture
def anon_drf_client():
    """Just return an API client without a session."""

    return APIClient()


@pytest.mark.parametrize(
    "is_program",
    [
        True,
        False,
    ],
)
def test_serialize_certificate(is_program):
    """Test that the certificate serializes properly."""

    if is_program:
        courseware_page = ProgramPageFactory.create()
    else:
        courseware_page = CoursePageFactory.create()

    cert_page = courseware_page.certificate_page
    cert_page.save_revision()  # we need at least one

    if is_program:
        certificate = ProgramCertificateFactory.create(
            certificate_page_revision=cert_page.revisions.last()
        )
        serialized_data = ProgramCertificateSerializer(certificate).data
    else:
        certificate = CourseRunCertificateFactory.create(
            certificate_page_revision=cert_page.revisions.last()
        )
        serialized_data = CourseRunCertificateSerializer(certificate).data

    expected_data = {
        "user": PublicUserSerializer(certificate.user).data,
        "uuid": certificate.uuid,
        "is_revoked": certificate.is_revoked,
        "certificate_page_revision": cert_page.revisions.last().id,
        "certificate_page": {
            "id": cert_page.id,
            "meta": {
                "type": "cms.CertificatePage",
                "detail_url": reverse(
                    "wagtailapi:pages:detail", kwargs={"pk": cert_page.id}
                ),
                "html_url": cert_page.full_url,
                "slug": cert_page.page_ptr.slug,
                "show_in_menus": cert_page.page_ptr.show_in_menus,
                "seo_title": cert_page.page_ptr.seo_title,
                "search_description": cert_page.page_ptr.search_description,
                "first_published_at": cert_page.page_ptr.first_published_at,
                "alias_of": cert_page.page_ptr.alias_of,
                "locale": cert_page.page_ptr.locale.language_code,
                "live": cert_page.page_ptr.live,
                "last_published_at": cert_page.page_ptr.last_published_at,
            },
            "title": cert_page.title,
            "product_name": cert_page.product_name,
            "CEUs": cert_page.CEUs,
            "overrides": [],
            "signatory_items": cert_page.signatory_items,
        },
    }

    if is_program:
        expected_data["program"] = ProgramSerializer(certificate.program).data
    else:
        expected_data["course_run"] = CourseRunWithCourseSerializer(
            certificate.course_run
        ).data

    assert_drf_json_equal(expected_data, serialized_data, ignore_order=True)
