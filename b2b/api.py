"""API functions for B2B operations."""

import logging

import reversion
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from mitol.common.utils import now_in_utc
from wagtail.models import Page

from b2b.constants import B2B_RUN_TAG_FORMAT
from b2b.models import ContractPage, OrganizationIndexPage, OrganizationPage
from cms.api import get_home_page
from courses.models import Course, CourseRun
from ecommerce.models import Product
from main.utils import date_to_datetime

log = logging.getLogger(__name__)


def ensure_b2b_organization_index() -> OrganizationIndexPage:
    """
    Ensures that an index page has been created for signatories.
    """
    home_page = get_home_page()
    org_index_page = Page.objects.filter(
        content_type=ContentType.objects.get_for_model(OrganizationIndexPage)
    ).first()
    if not org_index_page:
        org_index_page = OrganizationIndexPage(title="Organizations")
        home_page.add_child(instance=org_index_page)
        org_index_page.save_revision().publish()

    if org_index_page.get_children_count() != OrganizationPage.objects.count():
        for org_page in OrganizationPage.objects.all():
            org_page.move(org_index_page, "last-child")
        log.info("Moved organization pages under organization index page")
    return org_index_page


def create_contract_run(
    contract: ContractPage, course: Course
) -> tuple[CourseRun, Product]:
    """
    Create a run for the specified contract.

    Contract runs are always self-paced. Dates align with the contract - start
    and end dates are set to the contract's start and end dates and the
    certificate available date is set to the start date of the contract. If the
    contract has no dates, then the start dates get set to today. The run tag
    will be generated according to the contract and org IDs.

    This will also create a product for the run. The product will have zero
    value (unless the contract specifies one).

    This won't create pages for either the run or the products, since they're
    not supposed to be accessed by the public.

    - For now this won't check the contract for pricing, since we're not doing
    that yet.
    - This should also create the run in edX, but we also don't do that yet.
      When we add that, we should backfill the URL into the course run.

    Args:
        contract (ContractPage): The contract to create the run for.
        course (Course): The course for which we should create a run.
    Returns:
        CourseRun: The created CourseRun object.
        Product: The created Product object.
    """

    run_tag = B2B_RUN_TAG_FORMAT.format(
        contract_id=contract.id,
        org_id=contract.get_parent().id,
    )

    # Check first for an existing run with the same tag.
    if CourseRun.objects.filter(course=course, b2b_contract=contract).exists():
        msg = f"Can't create a run for {course} and contract {contract}: run tag {run_tag} already exists."
        raise ValueError(msg)

    start_date = (
        date_to_datetime(contract.contract_start, settings.TIME_ZONE)
        if contract.contract_start
        else now_in_utc()
    )
    end_date = (
        date_to_datetime(contract.contract_end, settings.TIME_ZONE)
        if contract.contract_end
        else None
    )

    course_run = CourseRun(
        course=course,
        title=course.title,
        courseware_id=f"{course.readable_id}+{run_tag}",
        run_tag=run_tag,
        start_date=start_date,
        end_date=end_date,
        enrollment_start=start_date,
        enrollment_end=end_date,
        certificate_available_date=start_date,
        is_self_paced=True,
        live=True,
        b2b_contract=contract,
        courseware_url_path=settings.SITE_BASE_URL,
    )
    course_run.save()

    log.debug(
        "Created run %s for course %s in contract %s", course_run, course, contract
    )

    content_type = ContentType.objects.filter(
        app_label="courses", model="courserun"
    ).get()

    with reversion.create_revision():
        course_run_product = Product(
            price=0,
            is_active=True,
            description=f"{contract.organization.name} - {course.title} {course.readable_id}",
            object_id=course_run.id,
            content_type=content_type,
        )
        course_run_product.save()

        log.debug(
            "Created product %s for run %s in contract %s",
            course_run_product,
            course_run,
            contract,
        )

    return course_run, course_run_product
