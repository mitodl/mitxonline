"""Wagtail page factories"""
import factory
import wagtail_factories

from cms.models import HomePage


class HomePageFactory(wagtail_factories.PageFactory):
    """HomePage factory class"""

    hero = factory.SubFactory(wagtail_factories.ImageFactory)

    class Meta:
        model = HomePage
