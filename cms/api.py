"""API functionality for the CMS app"""

from __future__ import annotations

import logging
import random
from datetime import timedelta
from typing import Tuple, Union  # noqa: UP035
from urllib.parse import urlencode, urljoin

import requests
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.cache import caches
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.files.base import ContentFile
from django.db.models import Case, IntegerField, When
from django.utils.text import slugify
from mitol.common.utils import now_in_utc
from wagtail.blocks import StreamValue
from wagtail.images.models import Image
from wagtail.models import Site
from wagtail.rich_text import RichText

from cms import models as cms_models
from cms.constants import CERTIFICATE_INDEX_SLUG, INSTRUCTOR_INDEX_SLUG
from cms.exceptions import WagtailSpecificPageError
from cms.models import Page
from courses.models import Course, Program
from courses.utils import (
    get_enrollable_courseruns_qs,
)

log = logging.getLogger(__name__)
DEFAULT_HOMEPAGE_PROPS = dict(  # noqa: C408
    title="Home Page",
    hero_title="Lorem ipsum dolor",
    hero_subtitle="Enim ad minim veniam, quis nostrud exercitation",
)
DEFAULT_SITE_PROPS = dict(hostname="localhost", port=80)  # noqa: C408
COURSE_INDEX_PAGE_PROPERTIES = dict(title="Courses")  # noqa: C408
RESOURCE_PAGE_TITLES = [
    "About Us",
    "Terms of Service",
    "Privacy Policy",
    "Honor Code",
]
RESOURCE_PAGE_SLUGS = [slugify(title) for title in RESOURCE_PAGE_TITLES]
PROGRAM_INDEX_PAGE_PROPERTIES = dict(title="Programs")  # noqa: C408


def get_home_page(raise_if_missing=True, check_specific=False) -> Page:  # noqa: FBT002
    """
    Returns an instance of the home page (all of our Wagtail pages are expected to be descendants of this home page)

    Returns:
        Page: The home page object
    """
    home_page = Page.objects.filter(
        content_type=ContentType.objects.get_for_model(cms_models.HomePage), live=True
    ).first()
    if raise_if_missing is True and home_page is None:
        raise Page.DoesNotExist
    if check_specific and home_page is not None:
        try:
            home_page.get_specific()
        except cms_models.HomePage.DoesNotExist as exc:
            raise WagtailSpecificPageError(
                spec_page_cls=cms_models.HomePage, page_obj=home_page
            ) from exc
    return home_page


def _create_resource_page(title: str) -> cms_models.ResourcePage:
    """Creates a resource page with the given title under the parent page"""
    page = cms_models.ResourcePage(
        slug=slugify(title),
        title=title,
    )
    page.content.append(
        (
            "content",
            {
                "heading": title,
                "detail": RichText(f"<p>Stock {title.lower()} page.</p>"),
            },
        )
    )
    return page


def ensure_resource_pages() -> None:
    """
    Ensures that a set of specific resource pages exist in some basic form
    """
    home_page = get_home_page()
    resource_pages_qset = cms_models.ResourcePage.objects.filter(
        slug__in=RESOURCE_PAGE_SLUGS
    )
    if resource_pages_qset.count() == len(RESOURCE_PAGE_SLUGS):
        return
    existing_resource_titles = set(resource_pages_qset.values_list("title", flat=True))
    missing_resource_titles = set(RESOURCE_PAGE_TITLES) - existing_resource_titles
    for resource_page_title in missing_resource_titles:
        resource_page = _create_resource_page(resource_page_title)
        home_page.add_child(instance=resource_page)
        resource_page.save_revision().publish()


def ensure_home_page_and_site() -> Tuple[cms_models.HomePage, Site]:  # noqa: UP006
    """
    Ensures that Wagtail is configured with a home page of the right type, and that
    the home page is configured as the default site.
    """
    site = Site.objects.filter(is_default_site=True).first()
    home_page = get_home_page(raise_if_missing=False, check_specific=True)
    root = Page.objects.get(depth=1)
    if home_page is None:
        home_page = cms_models.HomePage(**DEFAULT_HOMEPAGE_PROPS)
        root.add_child(instance=home_page)
        home_page.refresh_from_db()
        specific_home_page = home_page
    else:
        specific_home_page = home_page.specific
    if site is None:
        Site.objects.create(
            is_default_site=True, root_page=home_page, **DEFAULT_SITE_PROPS
        )
    elif site.root_page is None or site.root_page != home_page:
        site.root_page = home_page
        site.save()
        log.info("Updated site: %s", site)
    wagtail_default_home_page = Page.objects.filter(
        depth=2, content_type=ContentType.objects.get_for_model(Page)
    ).first()
    if wagtail_default_home_page is not None:
        wagtail_default_home_page.delete()
    return specific_home_page, site


def ensure_product_index() -> cms_models.CourseIndexPage:
    """
    Ensures that an index page has been created for each type of product, and that all product pages are
    nested under it.
    """
    home_page = get_home_page()
    course_index = Page.objects.filter(
        content_type=ContentType.objects.get_for_model(cms_models.CourseIndexPage)
    ).first()
    if not course_index:
        course_index = cms_models.CourseIndexPage(**COURSE_INDEX_PAGE_PROPERTIES)
        home_page.add_child(instance=course_index)
        course_index.save_revision().publish()
    # Move course detail pages to be children of the course index pages
    for page_id in cms_models.CoursePage.objects.exclude(
        path__startswith=course_index.path
    ).values_list("id", flat=True):
        page = Page.objects.get(id=page_id)
        page.move(course_index, "last-child")
    return course_index


def ensure_program_product_index() -> cms_models.ProgramIndexPage:
    """
    Same as ensure_product_index, but operates on programs instead.
    """
    home_page = get_home_page()
    program_index = Page.objects.filter(
        content_type=ContentType.objects.get_for_model(cms_models.ProgramIndexPage)
    ).first()
    if not program_index:
        program_index = cms_models.ProgramIndexPage(**PROGRAM_INDEX_PAGE_PROPERTIES)
        home_page.add_child(instance=program_index)
        program_index.save_revision().publish()
    # Move course detail pages to be children of the course index pages
    for page_id in cms_models.ProgramPage.objects.exclude(
        path__startswith=program_index.path
    ).values_list("id", flat=True):
        page = Page.objects.get(id=page_id)
        page.move(program_index, "last-child")
    return program_index


def ensure_program_collection_index() -> cms_models.ProgramCollectionIndexPage:
    """
    Ensures that an index page has been created for program collections.
    """
    home_page = get_home_page()
    program_collection_index = Page.objects.filter(
        content_type=ContentType.objects.get_for_model(
            cms_models.ProgramCollectionIndexPage
        )
    ).first()
    if not program_collection_index:
        program_collection_index = cms_models.ProgramCollectionIndexPage(
            title="Program Collections"
        )
        home_page.add_child(instance=program_collection_index)
        program_collection_index.save_revision().publish()
    return program_collection_index


def ensure_signatory_index() -> cms_models.SignatoryIndexPage:
    """
    Ensures that an index page has been created for signatories.
    """
    home_page = get_home_page()
    signatory_index = Page.objects.filter(
        content_type=ContentType.objects.get_for_model(cms_models.SignatoryIndexPage)
    ).first()
    if not signatory_index:
        signatory_index = cms_models.SignatoryIndexPage(title="Signatories")
        home_page.add_child(instance=signatory_index)
        signatory_index.save_revision().publish()

    if signatory_index.get_children_count() != cms_models.SignatoryPage.objects.count():
        for signatory_page in cms_models.SignatoryPage.objects.all():
            signatory_page.move(signatory_index, "last-child")
        log.info("Moved signatory pages under signatory index page")
    return signatory_index


def ensure_certificate_index() -> cms_models.CertificateIndexPage:
    """
    Ensures that an index page has been created for certificates.
    """
    home_page = get_home_page()
    certificate_index = cms_models.CertificateIndexPage.objects.first()

    if certificate_index and certificate_index.slug != CERTIFICATE_INDEX_SLUG:
        certificate_index.slug = CERTIFICATE_INDEX_SLUG
        certificate_index.save()

    if not certificate_index:
        cert_index_content_type, _ = ContentType.objects.get_or_create(
            app_label="cms", model="certificateindexpage"
        )
        certificate_index = cms_models.CertificateIndexPage(
            title="Certificate Index Page",
            content_type_id=cert_index_content_type.id,
            slug=CERTIFICATE_INDEX_SLUG,
        )
        home_page.add_child(instance=certificate_index)
    return certificate_index


def ensure_instructors_index() -> cms_models.InstructorIndexPage:
    """
    Ensures that an index page has been created for instructors.
    """
    home_page = get_home_page()
    instructor_index = cms_models.InstructorIndexPage.objects.first()

    if instructor_index and instructor_index.slug != INSTRUCTOR_INDEX_SLUG:
        instructor_index.slug = INSTRUCTOR_INDEX_SLUG
        instructor_index.save()

    if not instructor_index:
        instructor_index_content_type, _ = ContentType.objects.get_or_create(
            app_label="cms", model="instructorindexpage"
        )
        instructor_index = cms_models.InstructorIndexPage(
            title="Instructors",
            content_type_id=instructor_index_content_type.id,
            slug=INSTRUCTOR_INDEX_SLUG,
        )
        home_page.add_child(instance=instructor_index)
    return instructor_index


def get_wagtail_img_src(image_obj) -> str:
    """Returns the image source URL for a Wagtail Image object"""
    if not image_obj or not image_obj.file:
        return ""

    root_rel = urljoin(settings.MEDIA_URL, image_obj.file.name)
    abs_url = urljoin(settings.SITE_BASE_URL, root_rel)
    return (
        "{url}?{qs}".format(
            url=abs_url,
            qs=urlencode({"v": image_obj.file_hash}),
        )
        if image_obj
        else ""
    )


def create_default_signatory_page(
    courseware: Union[Course, Program],
    *,
    include_placeholder_image: bool = False,
):
    # Import here to avoid circular imports
    from cms.models import SignatoryIndexPage, SignatoryPage  # noqa: PLC0415

    certificate_page = courseware.page.certificate_page
    signatory_page = SignatoryPage(
        name=f"PLACEHOLDER - {courseware.title} Signatory",
        title_1=f"PLACEHOLDER - {courseware.title} Signatory Title 1",
        title_2=f"PLACEHOLDER - {courseware.title} Signatory Title 2",
        title_3=f"PLACEHOLDER - {courseware.title} Signatory Title 3",
        organization=f"PLACEHOLDER - {courseware.title} Signatory Organization",
    )
    if include_placeholder_image:
        filename = signatory_page.name.replace(" ", "_").lower()
        image_url = f"https://placecats.com/{SignatoryPage.MINIMUM_IMAGE_WIDTH}/{SignatoryPage.MINIMUM_IMAGE_HEIGHT}"
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()
        image_file = ContentFile(response.content, name=filename)
        signatory_image = Image(title=filename, file=image_file)
        signatory_image.save()
        signatory_page.signature_image = signatory_image

    signatory_index = SignatoryIndexPage.objects.first()
    signatory_index.add_child(instance=signatory_page)
    signatory_page.refresh_from_db()

    signatories = StreamValue(
        certificate_page.signatories.stream_block,
        [("signatory", signatory_page)],
        is_lazy=False,
    )
    certificate_page.signatories = signatories
    certificate_page.save()
    return signatory_page


def create_default_certificate_page(
    courseware: Union[Course, Program],
):
    # Import here to avoid circular imports
    from cms.models import CertificatePage  # noqa: PLC0415

    cert_page = CertificatePage(
        product_name=f"PLACEHOLDER - {courseware.title} Certificate",
        CEUs=f"PLACEHOLDER - {courseware.title} CEUs",
    )
    courseware_page = courseware.page
    courseware_page.add_child(instance=cert_page)
    return cert_page


def get_optional_placeholder_values_for_courseware_type(
    courseware_type: Union[Course, Program],
) -> dict:
    """
    Returns a dictionary of optional values to include when creating the page,
    based on the type of courseware (Course or Program).
    """

    # Just some hardcoded example values for demonstration purposes.
    # Might make sense to use faker for some of this or allow selection of values from different presets
    # For now though, this sets up a page which is reasonably complete and can be immediately published
    values = {
        "price": [
            (
                "price_details",
                {
                    "text": "PLACEHOLDER - Three easy payments of 99.99",
                    "link": "https://example.com/pricing",
                },
            )
        ],
        "min_weeks": 1,
        "max_weeks": 1,
        "effort": "PLACEHOLDER - 1-2 hours per week",
        "length": "PLACEHOLDER - 1 week",
        "min_price": 37,
        "max_price": 149,
        "prerequisites": "PLACEHOLDER - No prerequisites, other than a willingness to learn",
        "faq_url": "https://example.com",
    }
    if isinstance(courseware_type, Course):
        values["about"] = (
            "PLACEHOLDER - In this engineering course, we will explore the processing and structure of cellular solids as they are created from polymers, metals, ceramics, glasses and composites."
        )
        values["what_you_learn"] = (
            "PLACEHOLDER - In this engineering course, we will explore the processing and structure of cellular solids as they are created from polymers, metals, ceramics, glasses and composites."
        )
    elif isinstance(courseware_type, Program):
        values["about"] = (
            "PLACEHOLDER - In this engineering program, we will explore the processing and structure of cellular solids as they are created from polymers, metals, ceramics, glasses and composites."
        )
        values["what_you_learn"] = (
            "PLACEHOLDER - In this engineering program, we will explore the processing and structure of cellular solids as they are created from polymers, metals, ceramics, glasses and composites."
        )

    return values


def create_default_courseware_page(
    courseware: Union[Course, Program],
    *,
    live: bool = False,
    include_in_learn_catalog: bool = False,
    ingest_content_files_for_ai: bool = False,
    optional_kwargs: dict | None = None,
):
    """
    Creates a default about page for the given courseware object. Created pages
    won't be in a published state (as this will put just the bare minimum in to
    make it work). The created page will exist in the proper part of the
    hierarchy, so this will fail if there's not an index page for the courseware
    object type. You cannot have duplicate pages for a courseware object, so
    trying to create one will result in an exception being raised.

    Args:
    - object (Course or Program): The courseware object to work with
    - live (boolean): Make the page live or not (default False)
    Keyword Args:
    - title (str): Force a specific title.
    - slug (str): Force a specific slug.
    Returns:
    - CoursePage or ProgramPage; the page
    Raises:
    - Exception
    """
    from cms.models import (  # noqa: PLC0415
        CourseIndexPage,
        CoursePage,
        ProgramIndexPage,
        ProgramPage,
    )

    page_framework = {
        "title": courseware.title,
        "description": courseware.title,
        "live": live,
        "length": "No Data",
        "slug": slugify(courseware.readable_id),
        "max_weekly_hours": "Empty",
        "min_weekly_hours": "Empty",
    }

    course_only_kwargs = {
        "include_in_learn_catalog": include_in_learn_catalog,
        "ingest_content_files_for_ai": ingest_content_files_for_ai,
    }
    program_only_kwargs = {}

    if optional_kwargs is None:
        optional_kwargs = {}

    try:
        if isinstance(courseware, Course):
            parent_page = CourseIndexPage.objects.filter(live=True).get()
        else:
            parent_page = ProgramIndexPage.objects.filter(live=True).get()
    except ObjectDoesNotExist:
        raise ValidationError(f"No valid index page found for {courseware}.")  # noqa: B904, EM102

    if isinstance(courseware, Course):
        merged_kwargs = page_framework | course_only_kwargs | optional_kwargs
        page = CoursePage(course=courseware, **merged_kwargs)
    else:
        merged_kwargs = page_framework | program_only_kwargs | optional_kwargs
        page = ProgramPage(program=courseware, **merged_kwargs)

    parent_page.add_child(instance=page)

    page.save()
    page.refresh_from_db()

    if isinstance(courseware, Course):
        homepage = cms_models.HomePage.objects.first()

        cms_models.HomeProductLink.objects.create(
            page=homepage, course_product_page=page
        )

    return page


def create_featured_items():
    """
    Pulls a new set of featured items for the CMS home page.
    Used only by cron task or management command.
    """
    redis_cache = caches["redis"]
    cache_key = "CMS_homepage_featured_courses"

    redis_cache.delete(cache_key)

    now = now_in_utc()
    end_of_day = now + timedelta(days=1)

    valid_course_ids = set(
        cms_models.CoursePage.objects.filter(live=True).values_list(
            "course_id", flat=True
        )
    )

    if not valid_course_ids:
        redis_cache.set(cache_key, [])
        return []

    enrollable_courses_qs = Course.objects.select_related("page").filter(
        id__in=valid_course_ids, live=True
    )
    enrollable_courseruns = (
        get_enrollable_courseruns_qs(end_of_day, enrollable_courses_qs)
        .select_related("course")
        .prefetch_related("course__page")
    )

    if not enrollable_courseruns.exists():
        redis_cache.set(cache_key, [])
        return []

    self_paced_runs = []
    regular_runs = []

    for courserun in enrollable_courseruns:
        if courserun.is_self_paced:
            self_paced_runs.append(courserun)
        else:
            regular_runs.append(courserun)

    random.shuffle(self_paced_runs)
    self_paced_course_ids = [run.course_id for run in self_paced_runs[:2]]

    random.shuffle(regular_runs)
    selected_regular_runs = regular_runs[:20]

    future_runs = []
    started_course_ids = []

    for courserun in selected_regular_runs:
        if courserun.start_date >= now:
            future_runs.append(courserun)
        else:
            started_course_ids.append(courserun.course_id)

    future_runs.sort(key=lambda cr: cr.start_date)
    future_course_ids = [run.course_id for run in future_runs]

    all_course_ids = self_paced_course_ids + future_course_ids + started_course_ids

    if not all_course_ids:
        redis_cache.set(cache_key, [])
        return []

    ordering = Case(
        *[When(id=cid, then=pos) for pos, cid in enumerate(all_course_ids)],
        output_field=IntegerField(),
    )

    # Store only course IDs to avoid pickling issues and ensure fresh data on retrieval
    redis_cache.set(cache_key, all_course_ids)

    return list(
        Course.objects.filter(id__in=all_course_ids)
        .select_related("page")
        .prefetch_related("courseruns")
        .order_by(ordering)
    )
