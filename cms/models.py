"""CMS model definitions"""
import re
from urllib.parse import quote_plus

from django.conf import settings
from django.db import models
from django.http import Http404
from django.urls import reverse
from wagtail.admin.edit_handlers import (
    FieldPanel,
    StreamFieldPanel,
    PageChooserPanel,
    InlinePanel,
)
from wagtail.core.blocks import StreamBlock
from wagtail.core.fields import RichTextField, StreamField
from wagtail.core.models import Page
from wagtail.core.models import Page, Orderable
from wagtail.images.models import Image
from wagtail.images.edit_handlers import ImageChooserPanel

from cms.blocks import ResourceBlock, PriceBlock, FacultyBlock

from modelcluster.fields import ParentalKey

from cms.constants import COURSE_INDEX_SLUG


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
    ]

    def _get_child_page_of_type(self, cls):
        """Gets the first child page of the given type if it exists"""
        child = self.get_children().type(cls).live().first()
        return child.specific if child else None

    @property
    def products(self):
        page_data = []
        for page in self.featured_products.all():
            if page.course_product_page:
                product_page = page.course_product_page.specific
                run = product_page.product.first_unexpired_run
                page_data.append(
                    {
                        "title": product_page.title,
                        "description": product_page.description,
                        "feature_image": product_page.feature_image,
                        "start_date": run.start_date if run is not None else None,
                        "url_path": product_page.get_url(),
                    }
                )
        return page_data

    def get_context(self, request, *args, **kwargs):
        return {
            **super().get_context(request),
            "product_cards_section_title": self.product_section_title,
            "products": self.products,
        }


class HomeProductLink(Orderable):
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
        blank=True, help_text="The description shown on the product page"
    )

    length = models.CharField(
        max_length=50,
        null=True,
        blank=True,
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
        blank=True,
        help_text="Specify the product price details.",
    )

    prerequisites = RichTextField(
        null=True,
        blank=True,
        help_text="A short description indicating prerequisites of this course.",
    )

    about = RichTextField(null=True, blank=True, help_text="About this course details.")

    what_you_learn = RichTextField(
        null=True, blank=True, help_text="What you will learn from this course."
    )

    feature_image = models.ForeignKey(
        Image,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Image that will be used where the course is featured or linked.",
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
        help_text="The faculty members to display on this page",
    )

    content_panels = Page.content_panels + [
        FieldPanel("description"),
        FieldPanel("length"),
        FieldPanel("effort"),
        FieldPanel("price"),
        FieldPanel("prerequisites"),
        FieldPanel("about"),
        FieldPanel("what_you_learn"),
        FieldPanel("feature_image"),
        FieldPanel("faculty_section_title"),
        StreamFieldPanel("faculty_members"),
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

    course = models.OneToOneField(
        "courses.Course", null=True, on_delete=models.SET_NULL, related_name="page"
    )

    @property
    def product(self):
        """Gets the product associated with this page"""
        return self.course

    template = "product_page.html"

    def get_context(self, request, *args, **kwargs):
        first_unexpired_run = self.product.first_unexpired_run
        is_enrolled = (
            False
            if (first_unexpired_run is None or not request.user.is_authenticated)
            else (
                first_unexpired_run.courserunenrollment_set.filter(
                    user_id=request.user.id
                ).exists()
            )
        )
        sign_in_url = (
            None
            if request.user.is_authenticated
            else f'{reverse("login")}?next={quote_plus(self.get_url())}'
        )
        return {
            **super().get_context(request, *args, **kwargs),
            "run": first_unexpired_run,
            "is_enrolled": is_enrolled,
            "sign_in_url": sign_in_url,
            "start_date": first_unexpired_run.start_date
            if first_unexpired_run
            else None,
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
            "site_name": settings.SITE_NAME,
        }
