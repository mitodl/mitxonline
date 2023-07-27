"""CMS model definitions"""
import json
import logging
import re
from datetime import datetime, timedelta
from json import dumps
from urllib.parse import quote_plus

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.forms import ChoiceField, DecimalField
from django.http import Http404
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.text import slugify
from mitol.common.utils.datetime import now_in_utc
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, InlinePanel, PageChooserPanel
from wagtail.blocks import PageChooserBlock, StreamBlock
from wagtail.contrib.forms.forms import FormBuilder
from wagtail.contrib.forms.models import (
    FORM_FIELD_CHOICES,
    AbstractForm,
    AbstractFormField,
    AbstractFormSubmission,
)
from wagtail.contrib.routable_page.models import RoutablePageMixin, route
from wagtail.coreutils import WAGTAIL_APPEND_SLASH
from wagtail.embeds.embeds import get_embed
from wagtail.embeds.exceptions import EmbedException
from wagtail.fields import RichTextField, StreamField
from wagtail.images.models import Image
from wagtail.models import Orderable, Page, Site
from wagtail.search import index

from cms.blocks import (
    CourseRunCertificateOverrides,
    FacultyBlock,
    PriceBlock,
    ResourceBlock,
    validate_unique_readable_ids,
)
from cms.constants import (
    CERTIFICATE_INDEX_SLUG,
    COURSE_INDEX_SLUG,
    INSTRUCTOR_INDEX_SLUG,
    PROGRAM_INDEX_SLUG,
    SIGNATORY_INDEX_SLUG,
)
from cms.forms import CertificatePageForm
from courses.api import get_user_relevant_course_run, get_user_relevant_course_run_qset
from courses.models import Course, CourseRunCertificate, Program, ProgramCertificate
from flexiblepricing.api import (
    determine_auto_approval,
    determine_courseware_flexible_price_discount,
    determine_income_usd,
    determine_tier_courseware,
    is_courseware_flexible_price_approved,
)
from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.exceptions import NotSupportedException
from flexiblepricing.models import (
    CurrencyExchangeRate,
    FlexiblePrice,
    FlexiblePricingRequestSubmission,
)
from main.views import get_base_context

log = logging.getLogger()


class SignatoryObjectIndexPage(Page):
    """
    A placeholder class to group signatory object pages as children.
    This class logically acts as no more than a "folder" to organize
    pages and add parent slug segment to the page url.
    """

    class Meta:
        abstract = True

    parent_page_types = ["HomePage"]
    subpage_types = ["SignatoryPage"]

    @classmethod
    def can_create_at(cls, parent):
        """
        You can only create one of these pages under the home page.
        The parent is limited via the `parent_page_type` list.
        """
        return (
            super().can_create_at(parent)
            and not parent.get_children().type(cls).exists()
        )

    def serve(self, request, *args, **kwargs):
        """
        For index pages we raise a 404 because these pages do not have a template
        of their own and we do not expect a page to available at their slug.
        """
        raise Http404


class SignatoryIndexPage(SignatoryObjectIndexPage):
    """
    A placeholder page to group all the signatories under it as well
    as consequently add /signatories/ to the signatory page urls
    """

    slug = SIGNATORY_INDEX_SLUG


class CertificateIndexPage(RoutablePageMixin, Page):
    """
    Certificate index page placeholder that handles routes for serving
    certificates given by UUID
    """

    parent_page_types = ["HomePage"]
    subpage_types = []

    slug = CERTIFICATE_INDEX_SLUG

    @classmethod
    def can_create_at(cls, parent):
        """
        You can only create one of these pages under the home page.
        The parent is limited via the `parent_page_type` list.
        """
        return (
            super().can_create_at(parent)
            and not parent.get_children().type(cls).exists()
        )

    @route(r"^program/([A-Fa-f0-9-]+)/?$")
    def program_certificate(
        self, request, uuid, *args, **kwargs
    ):  # pylint: disable=unused-argument
        """
        Serve a program certificate by uuid
        """
        # Try to fetch a certificate by the uuid passed in the URL
        try:
            certificate = ProgramCertificate.objects.get(uuid=uuid)
        except ProgramCertificate.DoesNotExist:
            raise Http404()

        # Get a CertificatePage to serve this request
        certificate_page = (
            certificate.certificate_page_revision.as_object()
            if certificate.certificate_page_revision
            else (
                certificate.program.page.certificate_page
                if hasattr(certificate.program, "page") and certificate.program.page
                else None
            )
        )
        if not certificate_page:
            raise Http404()

        if not certificate.certificate_page_revision:
            # The certificate.save() is overridden,it associates the certificate
            # page revision with the user's program certificate object
            certificate.save()

        certificate_page.certificate = certificate
        return certificate_page.serve(request)

    @route(r"^([A-Fa-f0-9-]+)/?$")
    def course_certificate(
        self, request, uuid, *args, **kwargs
    ):  # pylint: disable=unused-argument
        """
        Serve a course certificate by uuid
        """
        # Try to fetch a certificate by the uuid passed in the URL
        try:
            certificate = CourseRunCertificate.objects.get(uuid=uuid)
        except CourseRunCertificate.DoesNotExist:
            raise Http404()

        # Get a CertificatePage to serve this request
        certificate_page = (
            certificate.certificate_page_revision.as_object()
            if certificate.certificate_page_revision
            else (
                certificate.course_run.course.page.certificate_page
                if certificate.course_run.course.page
                else None
            )
        )

        if not certificate_page:
            raise Http404()

        if not certificate.certificate_page_revision:
            certificate.save()
        certificate_page.certificate = certificate
        return certificate_page.serve(request)

    @route(r"^$")
    def index_route(self, request, *args, **kwargs):
        """
        The index page is not meant to be served/viewed directly
        """
        raise Http404()


class CourseProgramChildPage(Page):
    """
    Abstract page representing a child of Course/Program Page
    """

    class Meta:
        abstract = True

    parent_page_types = [
        "CoursePage",
        "HomePage",
    ]

    # disable promote panels, no need for slug entry, it will be autogenerated
    promote_panels = []

    @classmethod
    def can_create_at(cls, parent):
        # You can only create one of these page under course / program.
        return (
            super(CourseProgramChildPage, cls).can_create_at(parent)
            and parent.get_children().type(cls).count() == 0
        )

    def save(self, clean=True, user=None, log_action=False, **kwargs):
        # autogenerate a unique slug so we don't hit a ValidationError
        if not self.title:
            self.title = self.__class__._meta.verbose_name.title()
        self.slug = slugify("{}-{}".format(self.get_parent().id, self.title))
        super().save(clean=clean, user=user, log_action=log_action, **kwargs)

    def get_url_parts(self, request=None):
        """
        Override how the url is generated for course/program child pages
        """
        # Verify the page is routable
        url_parts = super().get_url_parts(request=request)

        if not url_parts:
            return None

        site_id, site_root, parent_path = self.get_parent().specific.get_url_parts(
            request=request
        )
        page_path = ""

        # Depending on whether we have trailing slashes or not, build the correct path
        if WAGTAIL_APPEND_SLASH:
            page_path = "{}{}/".format(parent_path, self.slug)
        else:
            page_path = "{}/{}".format(parent_path, self.slug)
        return (site_id, site_root, page_path)

    def serve(self, request, *args, **kwargs):
        """
        As the name suggests these pages are going to be children of some other page. They are not
        designed to be viewed on their own so we raise a 404 if someone tries to access their slug.
        """
        raise Http404


class CertificatePage(CourseProgramChildPage):
    """
    CMS page representing a Certificate.
    """

    template = "certificate_page.html"
    parent_page_types = ["CoursePage", "ProgramPage"]

    product_name = models.CharField(
        max_length=250,
        null=False,
        blank=False,
        help_text="Specify the course/program name.",
    )

    CEUs = models.CharField(
        max_length=250,
        null=True,
        blank=True,
        help_text="Optional text field for CEU (continuing education unit).",
    )

    signatories = StreamField(
        StreamBlock(
            [
                (
                    "signatory",
                    PageChooserBlock(required=True, target_model=["cms.SignatoryPage"]),
                )
            ],
            min_num=1,
            max_num=5,
        ),
        help_text="You can choose upto 5 signatories.",
        use_json_field=True,
    )

    overrides = StreamField(
        [("course_run", CourseRunCertificateOverrides())],
        blank=True,
        help_text="Overrides for specific runs of this Course/Program",
        validators=[validate_unique_readable_ids],
        use_json_field=True,
    )

    content_panels = [
        FieldPanel("product_name"),
        FieldPanel("CEUs"),
        FieldPanel("overrides"),
        FieldPanel("signatories"),
    ]

    base_form_class = CertificatePageForm

    class Meta:
        verbose_name = "Certificate"

    def __init__(self, *args, **kwargs):
        self.certificate = None
        super().__init__(*args, **kwargs)

    def save(self, clean=True, user=None, log_action=False, **kwargs):
        # auto generate a unique slug so we don't hit a ValidationError
        self.title = (
            self.__class__._meta.verbose_name.title()
            + " For "
            + self.get_parent().title
        )

        self.slug = slugify("certificate-{}".format(self.get_parent().id))
        Page.save(self, clean=clean, user=user, log_action=log_action, **kwargs)

    def serve(self, request, *args, **kwargs):
        """
        We need to serve the certificate template for preview.
        """
        return Page.serve(self, request, *args, **kwargs)

    @property
    def signatory_pages(self):
        """
        Extracts all the pages out of the `signatories` stream into a list
        """
        pages = []
        for block in self.signatories:  # pylint: disable=not-an-iterable
            if block.value:
                pages.append(block.value.specific)
        return pages

    @property
    def parent(self):
        """
        Get the parent of this page.
        """
        return self.get_parent().specific

    def get_context(self, request, *args, **kwargs):
        preview_context = {}
        context = {}

        if request.is_preview:
            preview_context = {
                "learner_name": "Anthony M. Stark",
                "start_date": self.parent.product.first_unexpired_run.start_date
                if self.parent.product.first_unexpired_run
                else datetime.now(),
                "end_date": self.parent.product.first_unexpired_run.end_date
                if self.parent.product.first_unexpired_run
                else datetime.now() + timedelta(days=45),
                "CEUs": self.CEUs,
            }
        elif self.certificate:
            # Verify that the certificate in fact is for this same course
            if self.parent.product.id != self.certificate.get_courseware_object_id():
                raise Http404()
            start_date, end_date = self.certificate.start_end_dates
            CEUs = self.CEUs

            for override in self.overrides:  # pylint: disable=not-an-iterable
                if (
                    override.value.get("readable_id")
                    == self.certificate.get_courseware_object_readable_id()
                ):
                    CEUs = override.value.get("CEUs")
                    break

            is_program_certificate = False
            if isinstance(self.certificate, ProgramCertificate):
                is_program_certificate = True

            context = {
                "uuid": self.certificate.uuid,
                "certificate_user": self.certificate.user,
                "learner_name": self.certificate.user.get_full_name(),
                "start_date": start_date,
                "end_date": end_date,
                "CEUs": CEUs,
                "is_program_certificate": is_program_certificate,
            }
        else:
            raise Http404()

        # The share image url needs to be absolute
        return {
            "site_name": settings.SITE_NAME,
            "share_image_width": "1665",
            "share_image_height": "1291",
            "share_text": "I just earned a certificate in {} from {}".format(
                self.product_name, settings.SITE_NAME
            ),
            **super().get_context(request, *args, **kwargs),
            **preview_context,
            **context,
        }


class FormField(AbstractFormField):
    """
    Adds support for the Country field (see FlexiblePricingFormBuilder below).
    """

    CHOICES = FORM_FIELD_CHOICES + (("country", "Country"),)

    page = ParentalKey(
        "FlexiblePricingRequestForm",
        on_delete=models.CASCADE,
        related_name="form_fields",
    )
    field_type = models.CharField(
        verbose_name="Field Type", max_length=20, choices=CHOICES
    )


class FlexiblePricingFormBuilder(FormBuilder):
    """
    Creates a Country field type that pulls its choices from the configured
    exchange rates in the system. (So, no exchange rate = no option.)
    """

    def create_number_field(self, field, options):
        options["error_messages"] = {
            "required": f"{options['label']} is a required field."
        }
        return DecimalField(**options)

    def create_country_field(self, field, options):
        exchange_rates = []

        for record in CurrencyExchangeRate.objects.all():
            desc = record.currency_code
            if record.description is not None and len(record.description) > 0:
                desc = "{code} - {code_description}".format(
                    code=record.currency_code, code_description=record.description
                )
            exchange_rates.append((record.currency_code, desc))

        options["choices"] = exchange_rates
        options["error_messages"] = {
            "required": f"{options['label']} is a required field."
        }
        return ChoiceField(**options)


class InstructorPage(Page):
    """
    Detail page for instructors.
    """

    subpage_types = []

    instructor_name = models.CharField(
        max_length=255,
        default="",
        help_text="The name of the instructor.",
    )

    instructor_title = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="The instructor's title (academic or otherwise).",
    )

    instructor_bio_short = RichTextField(
        null=True,
        blank=True,
        help_text="A short biography of the instructor. This will be shown in cards.",
    )

    instructor_bio_long = RichTextField(
        null=True, blank=True, help_text="A longer biography of the instructor."
    )

    feature_image = models.ForeignKey(
        Image,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Image that will be used where the instructor is featured or linked. (The recommended dimensions for the image are 375x244)",
    )

    content_panels = Page.content_panels + [
        FieldPanel("instructor_name"),
        FieldPanel("instructor_title"),
        FieldPanel("instructor_bio_short"),
        FieldPanel("instructor_bio_long"),
        FieldPanel("feature_image"),
    ]

    def serve(self, request, *args, **kwargs):
        """
        For index pages we raise a 404 because these pages do not have a template
        of their own and we do not expect a page to available at their slug.
        """
        raise Http404


class InstructorObjectIndexPage(Page):
    """
    A placeholder class to group instructor object pages as children.
    This class logically acts as no more than a "folder" to organize
    pages and add parent slug segment to the page url.
    """

    class Meta:
        abstract = True

    parent_page_types = ["HomePage"]
    subpage_types = ["InstructorPage"]

    @classmethod
    def can_create_at(cls, parent):
        """
        You can only create one of these pages under the home page.
        The parent is limited via the `parent_page_type` list.
        """
        return (
            super().can_create_at(parent)
            and not parent.get_children().type(cls).exists()
        )

    def serve(self, request, *args, **kwargs):
        """
        For index pages we raise a 404 because these pages do not have a template
        of their own and we do not expect a page to available at their slug.
        """
        raise Http404


class InstructorIndexPage(InstructorObjectIndexPage):
    """
    A placeholder page to group all the instructors under it as well
    as consequently add /instructors/ to the instructor page urls
    """

    slug = INSTRUCTOR_INDEX_SLUG


class InstructorPageLink(models.Model):
    page = ParentalKey(
        Page, on_delete=models.CASCADE, related_name="linked_instructors"
    )

    linked_instructor_page = models.ForeignKey(
        InstructorPage,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    order = models.SmallIntegerField(default=1, null=True, blank=True)

    panels = [
        PageChooserPanel("linked_instructor_page", "cms.InstructorPage"),
    ]


class HomePage(Page):
    """
    Site home page
    """

    template = "home_page.html"

    hero = models.ForeignKey(
        Image,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Main image displayed at the top of the home page. (The recommended dimensions for hero image are "
        "1920x400)",
    )
    hero_title = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="The title text to display in the hero section of the home page.",
    )
    hero_subtitle = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="The subtitle text to display in the hero section of the home page.",
    )

    product_section_title = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="The title text to display in the product cards section of the home page.",
    )

    content_panels = Page.content_panels + [
        FieldPanel("hero"),
        FieldPanel("hero_title"),
        FieldPanel("hero_subtitle"),
        FieldPanel("product_section_title"),
        InlinePanel("featured_products", label="Featured Products"),
    ]

    parent_page_types = [Page]
    subpage_types = [
        "CoursePage",
        "ResourcePage",
        "CourseIndexPage",
        "FlexiblePricingRequestForm",
        "CertificateIndexPage",
        "SignatoryIndexPage",
        "InstructorIndexPage",
    ]

    def _get_child_page_of_type(self, cls):
        """Gets the first child page of the given type if it exists"""
        child = self.get_children().type(cls).live().first()
        return child.specific if child else None

    @property
    def products(self):
        future_data = []
        past_data = []
        for page in self.featured_products.filter(course_product_page__live=True):
            if page.course_product_page:
                product_page = page.course_product_page.specific
                run = product_page.product.first_unexpired_run
                run_data = {
                    "title": product_page.title,
                    "description": product_page.description,
                    "feature_image": product_page.feature_image,
                    "start_date": run.start_date if run is not None else None,
                    "url_path": product_page.get_url(),
                }
                if run and run.start_date and run.start_date < now_in_utc():
                    past_data.append(run_data)
                else:
                    future_data.append(run_data)

        # sort future course run in ascending order
        page_data = sorted(
            future_data,
            key=lambda item: (item["start_date"] is None, item["start_date"]),
        )
        # sort past course run in descending order
        page_data.extend(
            sorted(
                past_data,
                key=lambda item: (item["start_date"] is None, item["start_date"]),
                reverse=True,
            )
        )
        return page_data

    def get_context(self, request, *args, **kwargs):
        return {
            **super().get_context(request),
            **get_base_context(request),
            "product_cards_section_title": self.product_section_title,
            "products": self.products,
        }


class HomeProductLink(models.Model):
    """
    Home and ProductPage Link
    """

    page = ParentalKey(
        HomePage, on_delete=models.CASCADE, related_name="featured_products"
    )

    course_product_page = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    panels = [
        PageChooserPanel("course_product_page", "cms.CoursePage"),
    ]


class CourseObjectIndexPage(Page):
    """
    A placeholder class to group courseware object pages as children.
    This class logically acts as no more than a "folder" to organize
    pages and add parent slug segment to the page url.
    """

    class Meta:
        abstract = True

    parent_page_types = ["HomePage"]

    @classmethod
    def can_create_at(cls, parent):
        """
        You can only create one of these pages under the home page.
        The parent is limited via the `parent_page_type` list.
        """
        return (
            super().can_create_at(parent)
            and not parent.get_children().type(cls).exists()
        )

    def get_child_by_readable_id(self, readable_id):
        """Fetch a child page by a Program/Course readable_id value"""
        raise NotImplementedError

    def route(self, request, path_components):
        if path_components:
            # request is for a child of this page
            child_readable_id = path_components[0]
            remaining_components = path_components[1:]

            try:
                # Try to find a child by the 'readable_id' of a Program/Course
                # instead of the page slug (as Wagtail does by default)
                subpage = self.get_child_by_readable_id(child_readable_id)
            except Page.DoesNotExist:
                raise Http404

            return subpage.specific.route(request, remaining_components)
        return super().route(request, path_components)

    def serve(self, request, *args, **kwargs):
        """
        For index pages we raise a 404 because these pages do not have a template
        of their own and we do not expect a page to available at their slug.
        """
        raise Http404


class CourseIndexPage(CourseObjectIndexPage):
    """
    An index page for CoursePages
    """

    slug = COURSE_INDEX_SLUG

    def get_child_by_readable_id(self, readable_id):
        """Fetch a child page by the related Course's readable_id value"""
        return self.get_children().get(coursepage__course__readable_id=readable_id)


class ProgramIndexPage(CourseObjectIndexPage):
    """Index page for ProgramPages."""

    slug = PROGRAM_INDEX_SLUG

    def get_child_by_readable_id(self, readable_id):
        """Fetch a child page by the related Program's readable_id value"""
        return self.get_children().get(programpage__program__readable_id=readable_id)


class ProductPage(Page):
    """
    Abstract detail page for course runs and any other "product" that a user can enroll in
    """

    class Meta:
        abstract = True

    description = RichTextField(
        help_text="The description shown on the home page and product page. The recommended character limit is 1000 characters. Longer entries may not display nicely on the page."
    )

    length = models.CharField(
        max_length=50,
        default="",
        help_text="A short description indicating how long it takes to complete (e.g. '4 weeks').",
    )

    effort = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="A short description indicating how much effort is required (e.g. 1-3 hours per week).",
    )

    price = StreamField(
        StreamBlock([("price_details", PriceBlock())], max_num=1),
        help_text="Specify the product price details.",
        use_json_field=True,
    )

    prerequisites = RichTextField(
        null=True,
        blank=True,
        help_text="A short description indicating prerequisites of this course.",
    )

    about = RichTextField(null=True, blank=True, help_text="About this course details.")

    video_url = models.URLField(
        null=True,
        blank=True,
        help_text="URL to the video to be displayed for this program/course. It can be an HLS or Youtube video URL.",
    )

    what_you_learn = RichTextField(
        null=True, blank=True, help_text="What you will learn from this course."
    )

    feature_image = models.ForeignKey(
        Image,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Image that will be used where the course is featured or linked. (The recommended dimensions for the image are 375x244)",
    )

    faculty_section_title = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        default="Meet your instructors",
        help_text="The title text to display in the faculty cards section of the product page.",
    )

    faculty_members = StreamField(
        [("faculty_member", FacultyBlock())],
        null=True,
        blank=True,
        help_text="The faculty members to display on this page",
        use_json_field=True,
    )

    def save(self, clean=True, user=None, log_action=False, **kwargs):
        """
        Updates related courseware object title.
        """
        courseware_object = None
        if self.is_course_page:
            courseware_object = getattr(self, "course")
        elif self.is_program_page:
            courseware_object = getattr(self, "program")
        courseware_object.title = self.title
        courseware_object.save()

        return super().save(clean=clean, user=user, log_action=log_action, **kwargs)

    def _get_child_page_of_type(self, cls):
        """Gets the first child page of the given type if it exists"""
        child = self.get_children().type(cls).live().first()
        return child.specific if child else None

    @property
    def certificate_page(self):
        """Gets the certificate child page"""
        return self._get_child_page_of_type(CertificatePage)

    @property
    def video_player_config(self):
        """Get configuration for video player"""

        if self.video_url:
            config = {"techOrder": ["html5"], "sources": [{"src": self.video_url}]}
            try:
                embed = get_embed(self.video_url)
                provider_name = embed.provider_name.lower()
                config["techOrder"] = [provider_name, *config["techOrder"]]
                config["sources"][0]["type"] = f"video/{provider_name}"

                # As per https://github.com/mitodl/mitxonline/issues/490 we want to use the same controls of youtube in
                # case of youtube videos for supporting closed captions. We can do it in two possible ways:
                # 1) We add "Track" key of type `Captions` to the config with a hosted or static transcript file URL
                # 2) Or we can just disable `video.js` self controls and enable all the youtube controls for the youtube
                # based videos with embedded support for the closed captioning.
                # The solution in #2 is used below.
                if provider_name == "youtube":
                    config["controls"] = False
                    config["youtube"] = {
                        "ytControls": 2,
                        "cc_load_policy": 1,
                        "cc_lang_pref": 1,
                    }

            except EmbedException:
                log.info(
                    f"The embed for the current url {self.video_url} is unavailable."
                )
            return dumps(config)

    @property
    def is_course_page(self):
        """Gets the product page type, this is used for sorting product pages."""
        return isinstance(self, CoursePage)

    @property
    def is_program_page(self):
        """Gets the product page type, this is used for sorting product pages."""
        return isinstance(self, ProgramPage)

    content_panels = Page.content_panels + [
        FieldPanel("description"),
        FieldPanel("length"),
        FieldPanel("effort"),
        FieldPanel("price"),
        FieldPanel("prerequisites"),
        FieldPanel("about"),
        FieldPanel("what_you_learn"),
        FieldPanel("feature_image"),
        InlinePanel("linked_instructors", label="Faculty Members"),
        FieldPanel("faculty_section_title"),
        FieldPanel("faculty_members"),
        FieldPanel("video_url"),
    ]

    subpage_types = ["FlexiblePricingRequestForm", "CertificatePage"]

    # Matches the standard page path that Wagtail returns for this page type.
    slugged_page_path_pattern = re.compile(r"(^.*/)([^/]+)(/?$)")

    @property
    def product(self):
        """Returns the courseware object (Course, Program) associated with this page"""
        raise NotImplementedError

    def get_url_parts(self, request=None):
        """
        Overrides base method for returning the parts of the URL for pages of this class

        Wagtail generates the 'page_path' part of the url tuple with the
        parent page slug followed by this page's slug (e.g.: "/courses/my-page-title").
        We want to generate that path with the parent page slug followed by the readable_id
        of the Course/Program instead (e.g.: "/courses/course-v1:edX+DemoX+Demo_Course")
        """
        url_parts = super().get_url_parts(request=request)
        if not url_parts:
            return None
        return (
            url_parts[0],
            url_parts[1],
            re.sub(
                self.slugged_page_path_pattern,
                r"\1{}\3".format(self.product.readable_id),
                url_parts[2],
            ),
        )

    @property
    def get_current_finaid(self):
        """
        Returns information about financial aid for the current learner.

        If the learner has a flexible pricing(financial aid) request that's
        approved, this should return the learner's adjusted price. If they
        don't, this should return the Page for the applicable request form.
        If they're not logged in, this should return None.
        """
        raise NotImplementedError

    def get_context(self, request, *args, **kwargs):
        instructors = [
            member.linked_instructor_page
            for member in self.linked_instructors.order_by("order").all()
        ]

        return {
            **super().get_context(request),
            **get_base_context(request),
            "instructors": instructors,
        }

    def get_context(self, request, *args, **kwargs):
        instructors = [
            member.linked_instructor_page
            for member in self.linked_instructors.order_by("order").all()
        ]

        return {
            **super().get_context(request),
            **get_base_context(request),
            "instructors": instructors,
        }


class CoursePage(ProductPage):
    """
    Detail page for courses
    """

    parent_page_types = ["CourseIndexPage"]

    course = models.OneToOneField(
        "courses.Course", null=True, on_delete=models.SET_NULL, related_name="page"
    )

    search_fields = Page.search_fields + [
        index.RelatedFields(
            "course",
            [
                index.AutocompleteField("readable_id"),
            ],
        )
    ]

    @property
    def product(self):
        """Gets the product associated with this page"""
        return self.course

    def get_current_finaid(self, request):
        """
        Returns information about financial aid for the current learner.

        Args:
            request: the current request
        Returns:
            None, or a tuple of the original price and the discount to apply
        """
        ecommerce_product = self.product.active_products
        if (
            is_courseware_flexible_price_approved(self.product, request.user)
            and ecommerce_product
        ):
            ecommerce_product = ecommerce_product.first()

            discount = determine_courseware_flexible_price_discount(
                ecommerce_product, request.user
            )

            if discount and discount.check_validity(request.user):
                log.debug(
                    f"price is {ecommerce_product.price}, discount is {discount.discount_product(ecommerce_product)}"
                )
                return (
                    ecommerce_product.price,
                    discount.discount_product(ecommerce_product),
                )

        return None

    template = "product_page.html"

    def get_admin_display_title(self):
        """Gets the title of the course in the specified format"""
        return f"{self.course.readable_id} | {self.title}"

    def get_context(self, request, *args, **kwargs):
        relevant_run = get_user_relevant_course_run(
            course=self.product, user=request.user
        )
        relevant_runs = list(
            get_user_relevant_course_run_qset(course=self.product, user=request.user)
        )
        is_enrolled = (
            False
            if (relevant_run is None or not request.user.is_authenticated)
            else (relevant_run.enrollments.filter(user_id=request.user.id).exists())
        )
        sign_in_url = (
            None
            if request.user.is_authenticated
            else f'{reverse("login")}?next={quote_plus(self.get_url())}'
        )
        start_date = relevant_run.start_date if relevant_run else None
        can_access_edx_course = (
            request.user.is_authenticated
            and relevant_run is not None
            and (relevant_run.is_in_progress or request.user.is_editor)
        )
        finaid_price = self.get_current_finaid(request)
        product = (
            relevant_run.products.filter(is_active=True).first()
            if relevant_run
            else None
        )
        return {
            **super().get_context(request, *args, **kwargs),
            **get_base_context(request),
            "run": relevant_run,
            "course_runs": relevant_runs,
            "is_enrolled": is_enrolled,
            "sign_in_url": sign_in_url,
            "start_date": start_date,
            "can_access_edx_course": can_access_edx_course,
            "finaid_price": finaid_price,
            "product": product,
        }

    content_panels = [
        FieldPanel("course"),
    ] + ProductPage.content_panels


class ProgramPage(ProductPage):
    """
    Detail page for programs
    """

    parent_page_types = ["ProgramIndexPage"]

    program = models.OneToOneField(
        "courses.Program", null=True, on_delete=models.SET_NULL, related_name="page"
    )

    search_fields = Page.search_fields + [
        index.RelatedFields(
            "program",
            [
                index.AutocompleteField("readable_id"),
            ],
        )
    ]

    @property
    def product(self):
        """Gets the product associated with this page"""
        return self.program

    template = "product_page.html"

    def get_admin_display_title(self):
        """Gets the title of the course in the specified format"""
        return f"{self.program.readable_id} | {self.title}"

    def get_context(self, request, *args, **kwargs):
        relevant_run = None
        is_enrolled = False
        sign_in_url = (
            None
            if request.user.is_authenticated
            else f'{reverse("login")}?next={quote_plus(self.get_url())}'
        )
        start_date = None
        can_access_edx_course = False
        return {
            **super().get_context(request, *args, **kwargs),
            **get_base_context(request),
            "run": relevant_run,
            "is_enrolled": is_enrolled,
            "sign_in_url": sign_in_url,
            "start_date": start_date,
            "can_access_edx_course": can_access_edx_course,
        }

    content_panels = [
        FieldPanel("program"),
    ] + ProductPage.content_panels


class ResourcePage(Page):
    """
    Basic resource page class for pages containing basic information (FAQ, etc.)
    """

    template = "resource_page.html"
    parent_page_types = ["HomePage"]
    subpage_types = ["FlexiblePricingRequestForm", "InnerResourcePage"]

    header_image = models.ForeignKey(
        Image,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Upload a header image that will render in the resource page. (The recommended dimensions for the image are 1920x300)",
    )

    content = StreamField(
        [("content", ResourceBlock())],
        blank=False,
        help_text="Enter details of content.",
        use_json_field=True,
    )

    content_panels = Page.content_panels + [
        FieldPanel("header_image"),
        FieldPanel("content"),
    ]

    def get_context(self, request, *args, **kwargs):
        return {
            **super().get_context(request, *args, **kwargs),
            **get_base_context(request),
            "site_name": settings.SITE_NAME,
        }


class InnerResourcePage(ResourcePage):
    """
    Interior page - same general format as ResourcePage, but can be nested under a ResourcePage
    """

    template = "resource_page.html"
    parent_page_types = ["ResourcePage"]


class FlexiblePricingRequestForm(AbstractForm):
    """
    Flexible Pricing request form. Allows learners to request flexible pricing
    for a given purchasable object (right now, just courses) or generally.

    On submission, this will create a FlexiblePrice record and will optionally
    link to a CoursePage if the form in question is a child page of one.
    """

    RICH_TEXT_FIELD_FEATURES = [
        "h1",
        "h2",
        "h3",
        "ol",
        "ul",
        "hr",
        "bold",
        "italic",
        "link",
        "document-link",
        "image",
        "embed",
    ]

    intro = RichTextField(blank=True)
    guest_text = RichTextField(
        null=True,
        blank=True,
        help_text="What to show if the user isn't logged in.",
    )

    selected_course = models.ForeignKey(
        Course, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    selected_program = models.ForeignKey(
        Program, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    application_processing_text = RichTextField(
        null=True,
        blank=True,
        help_text="What to show if the user's request is being processed.",
        features=RICH_TEXT_FIELD_FEATURES,
    )
    application_approved_text = RichTextField(
        null=True,
        blank=True,
        help_text="What to show if the user's request has been approved.",
        features=RICH_TEXT_FIELD_FEATURES,
    )
    application_approved_no_discount_text = RichTextField(
        null=True,
        blank=True,
        help_text="What to show if the user's request has been approved, but their discount is zero.",
        features=RICH_TEXT_FIELD_FEATURES,
    )
    application_denied_text = RichTextField(
        null=True,
        blank=True,
        help_text="What to show if the user's request has been denied.",
        features=RICH_TEXT_FIELD_FEATURES,
    )

    content_panels = AbstractForm.content_panels + [
        FieldPanel("intro"),
        FieldPanel("selected_course"),
        FieldPanel("selected_program"),
        FieldPanel("guest_text"),
        InlinePanel("form_fields", label="Form Fields"),
        FieldPanel("application_processing_text"),
        FieldPanel("application_approved_text"),
        FieldPanel("application_approved_no_discount_text"),
        FieldPanel("application_denied_text"),
    ]

    parent_page_types = [
        "cms.HomePage",
        "cms.ResourcePage",
        "cms.CoursePage",
        "cms.ProgramPage",
    ]

    form_builder = FlexiblePricingFormBuilder
    template = "flexiblepricing/flexible_pricing_request_form.html"
    landing_page_template = "flexiblepricing/flexible_pricing_request_form.html"

    def get_submission_class(self):
        return FlexiblePricingRequestSubmission

    def get_parent_product_page(self):
        """
        Returns the parent product (course or program) from the page that this
        form sits under.

        Flexible Price Request forms can be created as a child page for a
        course or program in the system. This looks at that and grabs the
        appropriate course page back (since get_parent returns a Page).

        Returns: CoursePage, ProgramPage, or None if not found
        """

        parent_page = self.get_parent()
        if CoursePage.objects.filter(page_ptr=parent_page).exists():
            return CoursePage.objects.filter(page_ptr=parent_page).get()

        if ProgramPage.objects.filter(page_ptr=parent_page).exists():
            return ProgramPage.objects.filter(page_ptr=parent_page).get()

        return None

    def get_parent_courseware(self):
        """
        Returns the valid courseware object that is associated with the form.
        The rules for this are:
        - If there's a Program selected, return that.
        - If there's a Course selected, return that.
        - If there's no selection, get the parent from get_parent_product_page.
          Then, repeat the first two steps.

        (At this point, there aren't Product pages so if it hits step 3 it will
        return a Course if there's one to be returned.)

        Updated 15-Jun: if we're considering a Course, and that course belongs
        to a Program, this will now return the first Program it belongs to.

        Returns:
            Course, Program, or None if not found
        """

        if (
            self.get_parent_product_page() is None
            and self.selected_course is None
            and self.selected_program is None
        ):
            return None
        elif self.selected_program is not None:
            return self.selected_program
        elif self.selected_course is not None:
            if len(self.selected_course.programs) > 0:
                return self.selected_course.programs[0]

            return self.selected_course
        elif isinstance(self.get_parent_product_page(), ProgramPage):
            return self.get_parent_product_page().program
        else:
            parent_page_course = self.get_parent_product_page().course
            return (
                parent_page_course
                if len(parent_page_course.programs) == 0
                else parent_page_course.programs[0]
            )

    def get_previous_submission(self, request):
        """
        Gets the last submission by the user for the courseware object the page
        is associated with. If the object is a Course that has an attached
        Program, this returns the first FlexiblePrice that's for either the
        Course or the Program.

        Updated 15-Jun-2023 jkachel: We will now look for submissions in any of
        the programs that the course belongs to.
        Updated 21-Jun-2023 jkachel: We will now look for submissions in any of
        the related programs of the programs that the course belongs to. (This
        will probably overlap with the above.)

        TODO: this logic will break when we have Program pages

        Returns:
            FlexiblePrice, or None if not found.
        """
        parent_courseware = self.get_parent_courseware()

        if parent_courseware is None or request.user.id is None:
            return None

        sub_qset = FlexiblePrice.objects.filter(user=request.user)
        course_ct = ContentType.objects.get(app_label="courses", model="course")
        program_ct = ContentType.objects.get(app_label="courses", model="program")

        if (
            isinstance(parent_courseware, Course)
            and len(parent_courseware.programs) > 0
        ):
            valid_submission_program_ids = []

            for program in parent_courseware.programs:
                valid_submission_program_ids.append(program.id)
                valid_submission_program_ids += [
                    related_program.id for related_program in program.related_programs
                ]

            sub_qset = sub_qset.filter(
                models.Q(
                    courseware_object_id=parent_courseware.id,
                    courseware_content_type=course_ct,
                )
                | models.Q(
                    courseware_object_id__in=valid_submission_program_ids,
                    courseware_content_type=program_ct,
                )
            )
        elif isinstance(parent_courseware, Program):
            sub_qset = sub_qset.filter(
                courseware_object_id__in=[parent_courseware.id]
                + [
                    related_program.id
                    for related_program in parent_courseware.related_programs
                ],
                courseware_content_type=program_ct,
            )
        else:
            sub_qset = sub_qset.filter(
                courseware_object_id=parent_courseware.id,
                courseware_content_type=course_ct
                if isinstance(parent_courseware, Course)
                else program_ct,
            )

        return sub_qset.order_by("-created_on").first()

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)

        fp_request = self.get_previous_submission(request)
        context["prior_request"] = fp_request
        product_page = self.get_parent_product_page()
        product = product_page.product
        context["product"] = (
            product.active_products.first()
            if isinstance(product, Course) and product.active_products is not None
            else None
        )
        context["product_page"] = product_page.url

        return context

    def serve(self, request, *args, **kwargs):
        previous_submission = self.get_previous_submission(request)
        if request.method == "POST" and (
            previous_submission is not None and not previous_submission.is_reset()
        ):
            form = self.get_form(page=self, user=request.user)

            context = self.get_context(request)
            context["form"] = form
            return TemplateResponse(request, self.get_template(request), context)

        return super().serve(request, *args, **kwargs)

    def process_form_submission(self, form):
        try:
            converted_income = determine_income_usd(
                float(form.cleaned_data["your_income"]),
                form.cleaned_data["income_currency"],
            )
        except NotSupportedException:
            raise ValidationError("Currency not supported")

        courseware = self.get_parent_courseware()
        income_usd = round(converted_income, 2)
        tier = determine_tier_courseware(courseware, income_usd)

        form_submission = self.get_submission_class().objects.create(
            form_data=json.dumps(form.cleaned_data, cls=DjangoJSONEncoder),
            page=self,
            user=form.user,
        )

        flexible_price = self.get_previous_submission(form)

        if flexible_price is None:
            flexible_price = FlexiblePrice(user=form.user, courseware_object=courseware)
        else:
            if flexible_price.status != FlexiblePriceStatus.RESET:
                raise ValidationError(
                    "A Flexible Price request already exists for this user and course or program."
                )

        flexible_price.original_income = form.cleaned_data["your_income"]
        flexible_price.original_currency = form.cleaned_data["income_currency"]
        flexible_price.country_of_income = form.user.legal_address.country
        flexible_price.income_usd = income_usd
        flexible_price.date_exchange_rate = datetime.now()
        flexible_price.cms_submission = form_submission
        flexible_price.tier = tier
        flexible_price.justification = ""

        if determine_auto_approval(flexible_price, tier) is True:
            flexible_price.status = FlexiblePriceStatus.AUTO_APPROVED
        else:
            flexible_price.status = FlexiblePriceStatus.PENDING_MANUAL_APPROVAL
        flexible_price.save()

    # Matches the standard page path that Wagtail returns for this page type.
    slugged_page_path_pattern = re.compile(r"(^.*/)([^/]+)(/?$)")

    def get_url_parts(self, request=None):
        """
        Overrides base method for returning the parts of the URL for pages of this class

        See the get_url_parts() method in CoursePage for the underlying theory
        here. If the form lives under a course or program page, though, this
        needs to respect the URL of that page or the form's action will be
        wrong.
        """
        if not self.get_parent_courseware():
            return super().get_url_parts(request=request)

        url_parts = self.get_parent_product_page().get_url_parts(request=request)
        if not url_parts:
            return None

        return (url_parts[0], url_parts[1], r"{}{}/".format(url_parts[2], self.slug))


class SignatoryPage(Page):
    """CMS page representing a Signatory."""

    promote_panels = []
    parent_page_types = [SignatoryIndexPage]
    subpage_types = []

    name = models.CharField(
        max_length=250, null=False, blank=False, help_text="Name of the signatory."
    )
    title_1 = models.CharField(
        max_length=250,
        null=True,
        blank=True,
        help_text="Specify signatory first title in organization.",
    )
    title_2 = models.CharField(
        max_length=250,
        null=True,
        blank=True,
        help_text="Specify signatory second title in organization.",
    )
    organization = models.CharField(
        max_length=250,
        null=True,
        blank=True,
        help_text="Specify the organization of signatory.",
    )

    signature_image = models.ForeignKey(
        Image,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Signature image size must be at least 150x50 pixels.",
    )

    class Meta:
        verbose_name = "Signatory"

    content_panels = [
        FieldPanel("name"),
        FieldPanel("title_1"),
        FieldPanel("title_2"),
        FieldPanel("organization"),
        FieldPanel("signature_image"),
    ]

    def save(self, clean=True, user=None, log_action=False, **kwargs):
        # auto generate a unique slug so we don't hit a ValidationError
        if not self.title:
            self.title = self.__class__._meta.verbose_name.title() + "-" + self.name

        self.slug = slugify("{}-{}".format(self.title, self.id))
        super().save(clean=clean, user=user, log_action=log_action, **kwargs)

    def serve(self, request, *args, **kwargs):
        """
        As the name suggests these pages are going to be children of some other page. They are not
        designed to be viewed on their own so we raise a 404 if someone tries to access their slug.
        """
        raise Http404
