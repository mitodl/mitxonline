"""CMS model definitions"""
import logging
import re
import datetime
import json
from urllib.parse import quote_plus

from json import dumps

from django.conf import settings
from django.db import models
from django.http import Http404
from django.urls import reverse
from django.forms import ChoiceField, DecimalField
from django.template.response import TemplateResponse
from django.contrib.contenttypes.models import ContentType

from mitol.common.utils.datetime import now_in_utc
from modelcluster.fields import ParentalKey
from wagtail.admin.edit_handlers import (
    FieldPanel,
    StreamFieldPanel,
    PageChooserPanel,
    InlinePanel,
)
from wagtail.core.blocks import StreamBlock
from wagtail.core.fields import RichTextField, StreamField
from wagtail.core.models import Page, Orderable
from wagtail.images.models import Image
from wagtail.images.edit_handlers import ImageChooserPanel
from wagtail.embeds.embeds import get_embed
from wagtail.embeds.exceptions import EmbedException
from wagtail.search import index
from wagtail.contrib.forms.forms import FormBuilder
from wagtail.contrib.forms.models import (
    AbstractForm,
    AbstractFormField,
    AbstractFormSubmission,
    FORM_FIELD_CHOICES,
)
from django.core.serializers.json import DjangoJSONEncoder

from cms.blocks import ResourceBlock, PriceBlock, FacultyBlock
from cms.constants import COURSE_INDEX_SLUG
from courses.api import get_user_relevant_course_run, get_user_relevant_course_run_qset
from courses.models import Course, Program
from main.views import get_base_context
from flexiblepricing.api import (
    determine_tier_courseware,
    determine_auto_approval,
    determine_income_usd,
)
from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.exceptions import NotSupportedException
from flexiblepricing.models import (
    CurrencyExchangeRate,
    FlexiblePrice,
    FlexiblePricingRequestSubmission,
)

log = logging.getLogger()


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
        ImageChooserPanel("hero"),
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
    ]

    def _get_child_page_of_type(self, cls):
        """Gets the first child page of the given type if it exists"""
        child = self.get_children().type(cls).live().first()
        return child.specific if child else None

    @property
    def products(self):
        future_data = []
        past_data = []
        for page in self.featured_products.all():
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
    )

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

    content_panels = Page.content_panels + [
        FieldPanel("description"),
        FieldPanel("length"),
        FieldPanel("effort"),
        StreamFieldPanel("price"),
        FieldPanel("prerequisites"),
        FieldPanel("about"),
        FieldPanel("what_you_learn"),
        ImageChooserPanel("feature_image"),
        FieldPanel("faculty_section_title"),
        StreamFieldPanel("faculty_members"),
        FieldPanel("video_url"),
    ]

    subpage_types = []

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


class CoursePage(ProductPage):
    """
    Detail page for courses
    """

    parent_page_types = ["CourseIndexPage"]
    subpage_types = ["cms.FlexiblePricingRequestForm"]

    course = models.OneToOneField(
        "courses.Course", null=True, on_delete=models.SET_NULL, related_name="page"
    )

    search_fields = Page.search_fields + [
        index.RelatedFields(
            "course",
            [
                index.SearchField("readable_id", partial_match=True),
            ],
        )
    ]

    @property
    def product(self):
        """Gets the product associated with this page"""
        return self.course

    template = "product_page.html"

    def get_admin_display_title(self):
        """Gets the title of the course in the specified format"""
        return f"{self.course.readable_id} | {self.title}"

    def get_context(self, request, *args, **kwargs):
        relevant_run = get_user_relevant_course_run(
            course=self.product, user=request.user
        )
        relevant_runs = list(
            get_user_relevant_course_run_qset(
                course=self.product, user=request.user
            ).values("courseware_id", "start_date")
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
        return {
            **super().get_context(request, *args, **kwargs),
            **get_base_context(request),
            "run": relevant_run,
            "course_runs": relevant_runs,
            "is_enrolled": is_enrolled,
            "sign_in_url": sign_in_url,
            "start_date": start_date,
            "can_access_edx_course": can_access_edx_course,
        }

    content_panels = [
        FieldPanel("course"),
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
    )

    content_panels = Page.content_panels + [
        ImageChooserPanel("header_image"),
        StreamFieldPanel("content"),
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
        FieldPanel("application_denied_text"),
    ]

    parent_page_types = ["cms.HomePage", "cms.ResourcePage", "cms.CoursePage"]

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

        Returns: CoursePage, or None if not found
        """
        # When program pages are in place, this should have some logic added to
        # grab other product types (program runs specifically).
        parent_page = self.get_parent()
        if CoursePage.objects.filter(page_ptr=parent_page).exists():
            coursepage = CoursePage.objects.filter(page_ptr=parent_page).get()
            return coursepage

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
            if self.selected_course.program is not None:
                return self.selected_course.program

            return self.selected_course
        else:
            parent_page_course = self.get_parent_product_page().course
            return (
                parent_page_course
                if parent_page_course.program is None
                else parent_page_course.program
            )

    def get_previous_submission(self, request):
        """
        Gets the last submission by the user for the courseware object the page
        is associated with. If the object is a Course that has an attached
        Program, this returns the first FlexiblePrice that's for either the
        Course or the Program.

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
            and parent_courseware.program is not None
        ):
            sub_qset = sub_qset.filter(
                models.Q(
                    courseware_object_id=parent_courseware.id,
                    courseware_content_type=course_ct,
                )
                | models.Q(
                    courseware_object_id=parent_courseware.program.id,
                    courseware_content_type=program_ct,
                )
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
            if flexible_price.status is not FlexiblePriceStatus.RESET:
                raise ValidationError(
                    "A Flexible Price request already exists for this user and course or program."
                )

        flexible_price.original_income = form.cleaned_data["your_income"]
        flexible_price.original_currency = form.cleaned_data["income_currency"]
        flexible_price.country_of_income = form.user.legal_address.country
        flexible_price.income_usd = income_usd
        flexible_price.date_exchange_rate = datetime.datetime.now()
        flexible_price.cms_submission = form_submission
        flexible_price.tier = tier

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
