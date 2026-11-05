"""Tests for cms forms"""

import pytest
from wagtail.test.utils.form_data import nested_form_data, streamfield

from cms.factories import (
    CertificatePageFactory,
    CoursePageFactory,
    SignatoryPageFactory,
)
from cms.models import CertificatePage

pytestmark = [pytest.mark.django_db]


def _certificate_page_form(should_provision, criteria):
    """Build a bound CertificatePage admin form with the given VC field values"""
    course_page = CoursePageFactory.create(certificate_page=None)
    certificate_page = CertificatePageFactory.create(parent=course_page)
    signatory = SignatoryPageFactory.create()
    form_class = CertificatePage.get_edit_handler().get_form_class()
    data = nested_form_data(
        {
            "title": certificate_page.title,
            "slug": certificate_page.slug,
            "product_name": "product_name",
            "signatories": streamfield([("signatory", signatory.id)]),
            "overrides": streamfield([]),
            "should_provision_verifiable_credential": should_provision,
            "verifiable_credential_criteria": criteria,
        }
    )
    return form_class(data, instance=certificate_page, parent_page=course_page)


@pytest.mark.parametrize(
    ("should_provision", "criteria"),
    [(True, "Completed the course"), (False, ""), (False, "Completed the course")],
)
def test_certificate_page_form_valid(should_provision, criteria):
    """
    The form should be valid unless provisioning is enabled without criteria
    Note that it's valid to have criteria specified without enabling provisioning
    (authors might still be iterating on the criteria and not want it actually enabled)
    """
    form = _certificate_page_form(should_provision, criteria)

    assert form.is_valid(), form.errors


def test_certificate_page_form_provisioning_requires_criteria():
    """Enabling provisioning without criteria should fail validation"""
    form = _certificate_page_form(should_provision=True, criteria="")

    assert not form.is_valid()
    assert form.errors["verifiable_credential_criteria"] == [
        "You must specify criteria if provisioning is enabled"
    ]
