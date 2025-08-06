"""Test factories for B2B models."""

from uuid import uuid4

import faker
import wagtail_factories
from factory import LazyAttribute, LazyFunction, SubFactory

from b2b.constants import CONTRACT_INTEGRATION_NONSSO, CONTRACT_INTEGRATION_SSO
from b2b.models import ContractPage, OrganizationIndexPage, OrganizationPage
from cms.factories import HomePageFactory
from cms.models import HomePage

FAKE = faker.Faker()


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

    name = LazyAttribute(lambda _: FAKE.unique.company())
    org_key = LazyAttribute(lambda _: FAKE.unique.text(max_nb_chars=5))
    description = LazyAttribute(lambda _: FAKE.unique.text())
    logo = None
    sso_organization_id = LazyAttribute(lambda _: uuid4())
    parent = LazyAttribute(
        lambda _: OrganizationIndexPage.objects.first()
        or OrganizationIndexPageFactory.create()
    )
    slug = LazyAttribute(lambda _: FAKE.unique.slug())

    class Meta:
        model = OrganizationPage


class ContractPageFactory(wagtail_factories.PageFactory):
    """ContractPage factory class"""

    name = LazyAttribute(lambda _: FAKE.unique.bs())
    description = LazyAttribute(lambda _: FAKE.unique.text())
    organization = SubFactory(OrganizationPageFactory)
    parent = LazyAttribute(lambda o: o.organization)
    integration_type = LazyFunction(
        lambda: CONTRACT_INTEGRATION_NONSSO
        if FAKE.boolean()
        else CONTRACT_INTEGRATION_SSO
    )
    slug = LazyAttribute(lambda _: FAKE.unique.slug())

    class Meta:
        model = ContractPage
