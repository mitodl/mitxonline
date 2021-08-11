"""Wagtail page factories"""
import factory
import wagtail_factories
from django.core.exceptions import ObjectDoesNotExist
from factory import fuzzy, LazyAttribute
from wagtail.core.models import Page

from cms.models import HomePage, CoursePage, ResourcePage, CourseIndexPage
from courses.factories import CourseFactory


class HomePageFactory(wagtail_factories.PageFactory):
    """HomePage factory class"""

    hero = factory.SubFactory(wagtail_factories.ImageFactory)

    class Meta:
        model = HomePage


class CoursePageFactory(wagtail_factories.PageFactory):
    """CoursePage factory class"""

    description = fuzzy.FuzzyText(prefix="Description ")
    feature_image = factory.SubFactory(wagtail_factories.ImageFactory)
    course = factory.SubFactory(CourseFactory)
    slug = fuzzy.FuzzyText(prefix="my-page-")
    parent = LazyAttribute(lambda _: CourseIndexPage.objects.first())

    class Meta:
        model = CoursePage


class ResourcePageFactory(wagtail_factories.PageFactory):
    """ResourcePage factory"""

    header_image = factory.SubFactory(wagtail_factories.ImageFactory)

    class Meta:
        model = ResourcePage
