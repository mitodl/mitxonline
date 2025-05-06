"""Test factories for B2B models."""

import faker
import wagtail_factories
from factory import LazyAttribute, LazyFunction, SubFactory

from b2b.constants import CONTRACT_INTEGRATION_NONSSO, CONTRACT_INTEGRATION_SSO
from b2b.models import ContractPage, OrganizationIndexPage, OrganizationPage
from cms.factories import HomePageFactory
from cms.models import HomePage

FAKE = faker.Factory.create()


class OrganizationIndexPageFactory(wagtail_factories.PageFactory):
    """OrganizationIndexPage factory class"""

    title = "Organizations"
    parent = LazyAttribute(
        lambda _: HomePage.objects.first() or HomePageFactory.create()
    )

    class Meta:
        model = OrganizationIndexPage


class OrganizationPageFactory(wagtail_factories.PageFactory):
    """OrganizationPage factory class"""

    name = FAKE.company()
    description = FAKE.text()
    logo = None
    parent = LazyAttribute(
        lambda _: OrganizationIndexPage.objects.first()
        or OrganizationIndexPageFactory.create()
    )

    class Meta:
        model = OrganizationPage


class ContractPageFactory(wagtail_factories.PageFactory):
    """ContractPage factory class"""

    name = FAKE.bs()
    description = FAKE.text()
    organization = SubFactory(OrganizationPageFactory)
    parent = LazyAttribute(lambda o: o.organization)
    integration_type = LazyFunction(
        lambda: CONTRACT_INTEGRATION_NONSSO
        if FAKE.boolean()
        else CONTRACT_INTEGRATION_SSO
    )

    class Meta:
        model = ContractPage
