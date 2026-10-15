"""Tests for the variant models"""

import pytest
from django.core.exceptions import ValidationError

from courses.factories import CourseRunFactory
from variants.models import SupportedVariant

pytestmark = [pytest.mark.django_db]


def test_clean_language():
    """
    Test that cleaning a VariantOptionsModel model works properly.

    The SupportedVariant model subclasses this so it works for this test. The
    goal is to make sure that the language field is validated properly.
    """

    test_cr = CourseRunFactory.create()
    test_variant = SupportedVariant.objects.create(
        variant_object=test_cr,
        default_variant=True,
        language="",
        variant_length="",
        variant_industry="",
    )

    test_variant.language = "ZZZ"

    with pytest.raises(ValidationError) as exc:
        test_variant.clean_language()

    assert "Course language is invalid" in str(exc)


@pytest.mark.parametrize(
    ("variant_length", "variant_industry", "length_label", "industry_label"),
    [
        ("", "", "Full", "Original"),
        ("S", "HC", "Short", "Healthcare"),
        ("", "M", "Full", "Manufacturing"),
    ],
)
def test_variant_labels(variant_length, variant_industry, length_label, industry_label):
    """The variant label properties return the display names for the codes."""

    run = CourseRunFactory.build(
        variant_length=variant_length, variant_industry=variant_industry
    )

    assert run.variant_length_label == length_label
    assert run.variant_industry_label == industry_label
