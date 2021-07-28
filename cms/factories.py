"""Wagtail page factories"""
import factory
import wagtail_factories
from factory import fuzzy

from cms.models import HomePage, CoursePage
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

    class Meta:
        model = CoursePage
