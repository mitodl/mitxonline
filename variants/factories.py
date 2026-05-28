"""Test factories for variants"""

import factory
from django.contrib.contenttypes.models import ContentType
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyChoice

from courses.constants import (
    COURSE_VARIANT_INDUSTRY,
    COURSE_VARIANT_LANGUAGE,
    COURSE_VARIANT_LENGTH,
)
from variants.models import SupportedVariant


class AbstractSupportedVariantFactory(DjangoModelFactory):
    """Variant factory with some reasonable defaults and support for generic relations."""

    language = FuzzyChoice([lang[0] for lang in COURSE_VARIANT_LANGUAGE])
    variant_industry = FuzzyChoice([ind[0] for ind in COURSE_VARIANT_INDUSTRY])
    variant_length = FuzzyChoice([lgt[0] for lgt in COURSE_VARIANT_LENGTH])
    object_id = factory.SelfAttribute("variant_object.id")
    content_type = factory.LazyAttribute(
        lambda o: ContentType.objects.get_for_model(o.variant_object)
    )

    class Meta:
        model = SupportedVariant
        abstract = True
        exclude = ["variant_object"]


class CourseSupportedVariantFactory(AbstractSupportedVariantFactory):
    """Variant factory for courses."""

    variant_object = factory.SubFactory("courses.factories.CourseFactory")


class ContractSupportedVariantFactory(AbstractSupportedVariantFactory):
    """Variant factory for contracts."""

    variant_object = factory.SubFactory("b2b.factories.ContractPageFactory")
