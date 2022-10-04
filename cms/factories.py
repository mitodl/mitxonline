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
    ProgramPage,
    ProgramIndexPage,
    CertificatePage,
    SignatoryPage,
)
from courses.factories import CourseFactory, ProgramFactory


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


class ProgramIndexPageFactory(wagtail_factories.PageFactory):
    """ProgramIndexPage factory class"""

    title = "Programs"
    parent = LazyAttribute(
        lambda _: HomePage.objects.first() or HomePageFactory.create()
    )

    class Meta:
        model = ProgramIndexPage


class CoursePageFactory(wagtail_factories.PageFactory):
    """CoursePage factory class"""

    description = fuzzy.FuzzyText(prefix="Description ")
    length = fuzzy.FuzzyText(prefix="Length ")
    feature_image = factory.SubFactory(wagtail_factories.ImageFactory)
    course = factory.SubFactory(CourseFactory, page=None)
    slug = fuzzy.FuzzyText(prefix="my-page-")
    parent = LazyAttribute(
        lambda _: CourseIndexPage.objects.first() or CourseIndexPageFactory.create()
    )
    certificate_page = factory.RelatedFactory(
        "cms.factories.CertificatePageFactory", "parent"
    )

    class Meta:
        model = CoursePage


class ProgramPageFactory(wagtail_factories.PageFactory):
    """ProgramPage factory class"""

    description = fuzzy.FuzzyText(prefix="Description ")
    length = fuzzy.FuzzyText(prefix="Length ")
    feature_image = factory.SubFactory(wagtail_factories.ImageFactory)
    program = factory.SubFactory(ProgramFactory, page=None)
    slug = fuzzy.FuzzyText(prefix="my-page-")
    parent = LazyAttribute(
        lambda _: ProgramIndexPage.objects.first() or ProgramIndexPageFactory.create()
    )
    certificate_page = factory.RelatedFactory(
        "cms.factories.CertificatePageFactory", "parent"
    )

    class Meta:
        model = ProgramPage


class ResourcePageFactory(wagtail_factories.PageFactory):
    """ResourcePage factory"""

    header_image = factory.SubFactory(wagtail_factories.ImageFactory)

    class Meta:
        model = ResourcePage


class FlexiblePricingFormFactory(wagtail_factories.PageFactory):
    intro = fuzzy.FuzzyText(prefix="Intro Text - ")
    guest_text = fuzzy.FuzzyText(prefix="Not Logged In - ")
    application_processing_text = fuzzy.FuzzyText(prefix="Application Processing - ")
    application_approved_text = fuzzy.FuzzyText(prefix="Application Approved - ")
    application_denied_text = fuzzy.FuzzyText(prefix="Application Denied - ")
    parent = LazyAttribute(
        lambda _: CoursePage.objects.first() or CoursePageFactory.create()
    )
    slug = fuzzy.FuzzyText(prefix="my-flex-price-form-")

    class Meta:
        model = FlexiblePricingRequestForm


class SignatoryPageFactory(wagtail_factories.PageFactory):
    """SignatoryPage factory class"""

    name = factory.fuzzy.FuzzyText(prefix="Name")
    title_1 = factory.fuzzy.FuzzyText(prefix="Title_1")
    title_2 = factory.fuzzy.FuzzyText(prefix="Title_2")
    organization = factory.fuzzy.FuzzyText(prefix="Organization")
    signature_image = factory.SubFactory(wagtail_factories.ImageFactory)

    class Meta:
        model = SignatoryPage


class CertificatePageFactory(wagtail_factories.PageFactory):
    """CertificatePage factory class"""

    product_name = factory.fuzzy.FuzzyText(prefix="product_name")
    CEUs = factory.Faker("pystr_format", string_format="#.#")
    signatories = wagtail_factories.StreamFieldFactory(
        {"signatory": SignatoryPageFactory}
    )

    class Meta:
        model = CertificatePage
