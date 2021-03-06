"""Wagtail page factories"""
import factory
import wagtail_factories
from django.core.exceptions import ObjectDoesNotExist
from factory import fuzzy, LazyAttribute
from wagtail.core.models import Page

from cms.models import (
    HomePage,
    CoursePage,
    ResourcePage,
    CourseIndexPage,
    FlexiblePricingRequestForm,
)
from courses.factories import CourseFactory


class HomePageFactory(wagtail_factories.PageFactory):
    """HomePage factory class"""

    hero = factory.SubFactory(wagtail_factories.ImageFactory)
    title = "Home Page"

    class Meta:
        model = HomePage


class CourseIndexPageFactory(wagtail_factories.PageFactory):
    """CourseIndexPage factory class"""

    title = "Courses"
    parent = LazyAttribute(
        lambda _: HomePage.objects.first() or HomePageFactory.create()
    )

    class Meta:
        model = CourseIndexPage


class CoursePageFactory(wagtail_factories.PageFactory):
    """CoursePage factory class"""

    description = fuzzy.FuzzyText(prefix="Description ")
    length = fuzzy.FuzzyText(prefix="Length ")
    feature_image = factory.SubFactory(wagtail_factories.ImageFactory)
    course = factory.SubFactory(CourseFactory)
    slug = fuzzy.FuzzyText(prefix="my-page-")
    parent = LazyAttribute(
        lambda _: CourseIndexPage.objects.first() or CourseIndexPageFactory.create()
    )

    class Meta:
        model = CoursePage


class ResourcePageFactory(wagtail_factories.PageFactory):
    """ResourcePage factory"""

    header_image = factory.SubFactory(wagtail_factories.ImageFactory)

    class Meta:
        model = ResourcePage


class FlexiblePricingFormFactory(wagtail_factories.PageFactory):
    intro = fuzzy.FuzzyText(prefix="Intro Text - ")
    thank_you_text = fuzzy.FuzzyText(prefix="Thank You - ")
    guest_text = fuzzy.FuzzyText(prefix="Not Logged In - ")
    application_processing_text = fuzzy.FuzzyText(prefix="Application Processing - ")
    application_approved_text = fuzzy.FuzzyText(prefix="Application Approved - ")
    application_denied_text = fuzzy.FuzzyText(prefix="Application Denied - ")
    parent = LazyAttribute(
        lambda _: CoursePage.objects.first() or CoursePageFactory.create()
    )

    class Meta:
        model = FlexiblePricingRequestForm
